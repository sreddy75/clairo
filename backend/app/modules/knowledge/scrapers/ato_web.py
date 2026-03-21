"""ATO website scraper for guides, forms, and general content.

Scrapes content from ATO website pages including:
- Business guides
- Tax topics
- Forms and instructions
- Help articles

Designed to work with specific URL patterns or sitemap-based discovery.
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from urllib.parse import urljoin

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)


# Default ATO sections to scrape
DEFAULT_ATO_SECTIONS = [
    "/businesses/",
    "/individuals/",
    "/not-for-profit/",
    "/super/",
]

# Content type detection patterns
CONTENT_TYPES = {
    "guide": [r"/guide", r"/how-to", r"/help"],
    "form": [r"/forms", r"/form-"],
    "calculator": [r"/calculator", r"/tool"],
    "factsheet": [r"/factsheet", r"/fact-sheet"],
    "news": [r"/news", r"/media-centre"],
}


class ATOWebScraper(BaseScraper):
    """Scraper for ATO website pages.

    Scrapes guides, forms, and other content from the ATO website.
    Can be configured with specific URLs or sections to crawl.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialize the ATO web scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific config with:
                - urls: List of specific URLs to scrape
                - sections: List of site sections to crawl
                - base_url: ATO base URL (default: https://www.ato.gov.au)
        """
        super().__init__(config, source_config)

        self._base_url = (
            source_config.get("base_url", "https://www.ato.gov.au")
            if source_config
            else "https://www.ato.gov.au"
        )

        self._urls = source_config.get("urls", []) if source_config else []
        self._sections = (
            source_config.get("sections", DEFAULT_ATO_SECTIONS)
            if source_config
            else DEFAULT_ATO_SECTIONS
        )

        # Max depth for crawling (0 = just the URLs provided)
        self._max_depth = source_config.get("max_depth", 1) if source_config else 1

    @property
    def source_type(self) -> str:
        return "ato_web"

    @property
    def collection_name(self) -> str:
        return "compliance_knowledge"

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Get URLs to scrape from configured sources.

        Yields:
            URLs to scrape.
        """
        # First, yield explicitly configured URLs
        for url in self._urls:
            yield self.make_absolute_url(self._base_url, url)

        # Then crawl sections if no explicit URLs provided
        if not self._urls:
            seen_urls: set[str] = set()

            for section in self._sections:
                section_url = urljoin(self._base_url, section)
                logger.info(f"Crawling ATO section: {section}")

                async for url in self._crawl_section(section_url, seen_urls, 0):
                    yield url

    async def _crawl_section(
        self,
        url: str,
        seen: set[str],
        depth: int,
    ) -> AsyncIterator[str]:
        """Crawl a section of the ATO website.

        Args:
            url: Starting URL.
            seen: Set of already seen URLs.
            depth: Current crawl depth.

        Yields:
            URLs found in the section.
        """
        if url in seen or depth > self._max_depth:
            return

        seen.add(url)
        yield url

        if depth >= self._max_depth:
            return

        # Fetch the page and extract links
        try:
            html = await self._fetch_url(url)
            if not html:
                return

            soup = self.clean_html(html)

            # Find links to other ATO pages
            for link in soup.find_all("a", href=True):
                href = link["href"]
                full_url = self.make_absolute_url(url, href)

                # Only follow ATO links
                if not full_url.startswith(self._base_url):
                    continue

                # Skip non-content URLs
                if self._should_skip_url(full_url):
                    continue

                if full_url not in seen:
                    async for sub_url in self._crawl_section(full_url, seen, depth + 1):
                        yield sub_url

        except Exception as e:
            logger.warning(f"Error crawling {url}: {e}")

    def _should_skip_url(self, url: str) -> bool:
        """Check if URL should be skipped.

        Args:
            url: URL to check.

        Returns:
            True if URL should be skipped.
        """
        skip_patterns = [
            r"\.pdf$",
            r"\.doc",
            r"\.xls",
            r"/login",
            r"/register",
            r"/myato",
            r"/search",
            r"#",
            r"\?",
        ]

        url_lower = url.lower()
        return any(re.search(pattern, url_lower) for pattern in skip_patterns)

    async def extract_content(self, url: str, html: str) -> ScrapedContent | None:
        """Extract content from an ATO page.

        Args:
            url: Page URL.
            html: Raw HTML.

        Returns:
            ScrapedContent or None.
        """
        soup = self.clean_html(html)

        # Extract title
        title = self.extract_title(soup)
        if not title:
            return None

        # Extract main content
        text = self._extract_ato_content(soup)
        if not text or len(text) < 200:
            logger.debug(f"Insufficient content for {url}")
            return None

        # Detect content type from URL and content
        source_type = self._detect_content_type(url, title)

        # Determine namespace based on URL path and content
        namespace = self._determine_namespace(url, title, text)

        # Extract entity types
        entity_types = self._extract_entity_types(text)

        # Extract last modified date
        modified_date = self._extract_modified_date(soup)

        return ScrapedContent(
            source_url=url,
            title=title,
            text=text,
            html=str(soup),
            source_type=source_type,
            collection_namespace=namespace,
            effective_date=modified_date,
            entity_types=entity_types,
            confidence_level="high" if "/businesses/" in url else "medium",
        )

    def _extract_ato_content(self, soup) -> str:
        """Extract main content from ATO page structure.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Extracted text.
        """
        # ATO-specific content selectors
        content_selectors = [
            "div.body-content",
            "div[data-component='body-content']",
            "article.content",
            "div.main-content",
            "main#main-content",
            "main",
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                # Remove breadcrumbs, nav, etc
                for unwanted in element.select(".breadcrumb, nav, .navigation"):
                    unwanted.decompose()

                text = element.get_text(separator="\n", strip=True)
                if len(text) > 200:
                    return text

        return self.extract_text(soup)

    def _detect_content_type(self, url: str, title: str) -> str:
        """Detect the type of content based on URL and title.

        Args:
            url: Page URL.
            title: Page title.

        Returns:
            Content type string.
        """
        url_title = (url + " " + title).lower()

        for content_type, patterns in CONTENT_TYPES.items():
            if any(re.search(p, url_title) for p in patterns):
                return f"ato_{content_type}"

        return "ato_guide"

    def _determine_namespace(self, url: str, title: str, text: str) -> str:
        """Determine the collection namespace.

        Args:
            url: Page URL.
            title: Page title.
            text: Page text.

        Returns:
            Namespace string.
        """
        combined = (url + " " + title + " " + text[:500]).lower()

        # GST
        if any(kw in combined for kw in ["gst", "goods and services tax"]):
            return "gst"

        # BAS
        if any(kw in combined for kw in ["bas", "business activity statement"]):
            return "bas"

        # Payroll
        if any(kw in combined for kw in ["payg", "withholding", "pay as you go", "payroll"]):
            return "payg"

        # Super
        if any(kw in combined for kw in ["super", "superannuation", "smsf"]):
            return "superannuation"

        # FBT
        if any(kw in combined for kw in ["fbt", "fringe benefit"]):
            return "fringe_benefits"

        # Income tax
        if any(kw in combined for kw in ["income tax", "tax return", "deduction"]):
            return "income_tax"

        # ABN
        if any(kw in combined for kw in ["abn", "australian business number"]):
            return "abn"

        return "general"

    def _extract_entity_types(self, text: str) -> list[str]:
        """Extract applicable entity types from content.

        Args:
            text: Page text.

        Returns:
            List of entity types.
        """
        text_lower = text.lower()
        entity_types = []

        entity_keywords = {
            "sole_trader": ["sole trader", "individual", "sole proprietor"],
            "company": ["company", "companies", "corporation", "pty ltd"],
            "trust": ["trust", "trustee", "beneficiary", "unit trust"],
            "partnership": ["partnership", "partner"],
            "smsf": ["self managed super", "smsf", "self-managed superannuation"],
        }

        for entity_type, keywords in entity_keywords.items():
            if any(kw in text_lower for kw in keywords):
                entity_types.append(entity_type)

        return entity_types if entity_types else ["all"]

    def _extract_modified_date(self, soup) -> datetime | None:
        """Extract last modified date from page.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Datetime or None.
        """
        # Try meta tags
        for prop in ["article:modified_time", "last-modified", "dcterms.modified"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                try:
                    return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except ValueError:
                    continue

        # Look for "Last modified" or "Updated" text
        text = soup.get_text()
        patterns = [
            r"(?:last\s+)?(?:modified|updated):?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
            r"(?:last\s+)?(?:modified|updated):?\s*(\d{1,2}\s+\w+\s+\d{4})",
        ]

        for pattern in patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d %B %Y", "%d %b %Y"]:
                        try:
                            return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Date parsing failed for '{match.group(1)}': {e}")
                    continue

        return None
