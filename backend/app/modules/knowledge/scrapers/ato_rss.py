"""ATO RSS feed scraper for tax rulings and news.

Scrapes content from ATO RSS feeds including:
- Tax Rulings (TR, GSTR, TD, PCG, etc.)
- News and updates
- Legal Database updates

The ATO provides RSS feeds at:
- https://www.ato.gov.au/rss/
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import feedparser

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)


# ATO RSS feed URLs
ATO_FEEDS = {
    "rulings": "https://www.ato.gov.au/rss/rulings.xml",
    "news": "https://www.ato.gov.au/rss/atonews.xml",
    "legal_database": "https://www.ato.gov.au/rss/legaldatabase.xml",
}

# Ruling number patterns
RULING_PATTERNS = {
    "TR": r"\bTR\s*\d{4}/\d+\b",  # Tax Ruling
    "GSTR": r"\bGSTR\s*\d{4}/\d+\b",  # GST Ruling
    "TD": r"\bTD\s*\d{4}/\d+\b",  # Tax Determination
    "PCG": r"\bPCG\s*\d{4}/\d+\b",  # Practical Compliance Guide
    "PS LA": r"\bPS\s*LA\s*\d{4}/\d+\b",  # Practice Statement Law Admin
    "CR": r"\bCR\s*\d{4}/\d+\b",  # Class Ruling
    "PR": r"\bPR\s*\d{4}/\d+\b",  # Private Ruling (public versions)
}

# Source type classification based on content
SOURCE_TYPE_KEYWORDS = {
    "ato_ruling": ["ruling", "determination", "tr ", "gstr", "td ", "pcg"],
    "ato_guide": ["guide", "information", "factsheet", "help"],
    "ato_news": ["news", "update", "announcement", "media"],
    "ato_alert": ["alert", "warning", "scam", "fraud"],
}


class ATORSSScraper(BaseScraper):
    """Scraper for ATO RSS feeds.

    Extracts tax rulings, news, and updates from ATO RSS feeds.
    Follows links to full content pages for extraction.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialize the ATO RSS scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific config with optional 'feeds' list.
        """
        super().__init__(config, source_config)

        # Get feeds to scrape from config or use defaults
        feed_keys = source_config.get("feeds", ["rulings"]) if source_config else ["rulings"]
        self._feeds = {k: ATO_FEEDS[k] for k in feed_keys if k in ATO_FEEDS}

        if not self._feeds:
            self._feeds = {"rulings": ATO_FEEDS["rulings"]}

    @property
    def source_type(self) -> str:
        return "ato_rss"

    @property
    def collection_name(self) -> str:
        return "compliance_knowledge"

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Get URLs from ATO RSS feeds.

        Yields:
            URLs to scrape from feed entries.
        """
        for feed_name, feed_url in self._feeds.items():
            logger.info(f"Fetching ATO RSS feed: {feed_name}")

            try:
                feed_content = await self.fetch_feed(feed_url)
                if not feed_content:
                    logger.warning(f"Empty feed response: {feed_name}")
                    continue

                # Parse the feed
                feed = feedparser.parse(feed_content)

                if feed.bozo:
                    logger.warning(f"Feed parsing issue: {feed.bozo_exception}")

                logger.info(f"Found {len(feed.entries)} entries in {feed_name}")

                for entry in feed.entries:
                    url = entry.get("link")
                    if url:
                        yield url

            except Exception as e:
                logger.error(f"Error fetching feed {feed_name}: {e}")
                continue

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
            logger.debug(f"No title found for {url}")
            return None

        # Extract main content
        text = self._extract_ato_content(soup)
        if not text or len(text) < 100:
            logger.debug(f"Insufficient content for {url}")
            return None

        # Detect source type from title and content
        source_type = self._classify_source_type(title, text)

        # Extract ruling number if present
        ruling_number = self._extract_ruling_number(title, text)

        # Determine collection namespace based on content
        namespace = self._determine_namespace(title, text, ruling_number)

        # Extract dates
        effective_date = self._extract_date(soup, "effective")

        # Determine entity types based on content
        entity_types = self._extract_entity_types(text)

        return ScrapedContent(
            source_url=url,
            title=title,
            text=text,
            html=str(soup),
            source_type=source_type,
            collection_namespace=namespace,
            effective_date=effective_date,
            ruling_number=ruling_number,
            entity_types=entity_types,
            confidence_level="high" if ruling_number else "medium",
        )

    def _extract_ato_content(self, soup) -> str:
        """Extract content from ATO page structure.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Extracted text content.
        """
        # ATO pages typically use these content containers
        content_selectors = [
            "div.body-content",
            "div.main-content",
            "article",
            "div.content",
            "main",
            "#main-content",
        ]

        for selector in content_selectors:
            element = soup.select_one(selector)
            if element:
                text = element.get_text(separator="\n", strip=True)
                if len(text) > 100:
                    return text

        # Fallback
        return self.extract_text(soup)

    def _classify_source_type(self, title: str, text: str) -> str:
        """Classify the source type based on content.

        Args:
            title: Page title.
            text: Page text.

        Returns:
            Source type string.
        """
        combined = (title + " " + text[:500]).lower()

        for source_type, keywords in SOURCE_TYPE_KEYWORDS.items():
            if any(keyword in combined for keyword in keywords):
                return source_type

        return "ato_general"

    def _extract_ruling_number(self, title: str, text: str) -> str | None:
        """Extract ruling number from content.

        Args:
            title: Page title.
            text: Page text.

        Returns:
            Ruling number or None.
        """
        # Check title first (most reliable)
        for _ruling_type, pattern in RULING_PATTERNS.items():
            match = re.search(pattern, title, re.IGNORECASE)
            if match:
                return match.group().replace(" ", "")

        # Then check first 500 chars of text
        text_start = text[:500]
        for _ruling_type, pattern in RULING_PATTERNS.items():
            match = re.search(pattern, text_start, re.IGNORECASE)
            if match:
                return match.group().replace(" ", "")

        return None

    def _determine_namespace(self, title: str, text: str, ruling_number: str | None) -> str:
        """Determine the collection namespace for the content.

        Args:
            title: Page title.
            text: Page text.
            ruling_number: Extracted ruling number.

        Returns:
            Namespace string (e.g., 'gst', 'income_tax', 'fringe_benefits').
        """
        combined = (title + " " + text[:1000]).lower()

        # GST related
        if "gst" in combined or (ruling_number and "GSTR" in ruling_number):
            return "gst"

        # FBT related
        if "fringe benefit" in combined or "fbt" in combined:
            return "fringe_benefits"

        # Super related
        if "superannuation" in combined or "super guarantee" in combined:
            return "superannuation"

        # Payroll related
        if any(kw in combined for kw in ["payg", "withholding", "pay as you go"]):
            return "payg"

        # Capital gains
        if "capital gain" in combined or "cgt" in combined:
            return "capital_gains"

        # Income tax (catch-all for tax-related)
        if any(kw in combined for kw in ["income tax", "tax return", "deduction"]):
            return "income_tax"

        return "general"

    def _extract_date(self, soup, date_type: str) -> datetime | None:
        """Extract date from page metadata or content.

        Args:
            soup: BeautifulSoup object.
            date_type: Type of date to extract ('effective', 'published', 'modified').

        Returns:
            Datetime or None.
        """
        # Try meta tags
        date_metas = {
            "effective": ["article:published_time", "datePublished"],
            "published": ["article:published_time", "datePublished", "DC.date.issued"],
            "modified": ["article:modified_time", "dateModified"],
        }

        for prop in date_metas.get(date_type, []):
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta and meta.get("content"):
                try:
                    return datetime.fromisoformat(meta["content"].replace("Z", "+00:00"))
                except ValueError:
                    continue

        # Try to find date in content
        text = soup.get_text()
        date_patterns = [
            r"(?:effective|from)\s*(?:date)?:?\s*(\d{1,2}[\/\-]\d{1,2}[\/\-]\d{4})",
            r"(\d{1,2}\s+(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{4})",
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text, re.IGNORECASE)
            if match:
                try:
                    date_str = match.group(1)
                    # Try multiple formats
                    for fmt in ["%d/%m/%Y", "%d-%m-%Y", "%d %B %Y"]:
                        try:
                            return datetime.strptime(date_str, fmt).replace(tzinfo=UTC)
                        except ValueError:
                            continue
                except Exception as e:
                    logger.debug(f"Date parsing failed for '{match.group(1)}': {e}")
                    continue

        return None

    def _extract_entity_types(self, text: str) -> list[str]:
        """Extract applicable entity types from content.

        Args:
            text: Page text.

        Returns:
            List of entity type strings.
        """
        text_lower = text.lower()
        entity_types = []

        entity_keywords = {
            "sole_trader": ["sole trader", "individual", "sole proprietor"],
            "company": ["company", "companies", "corporation", "pty ltd"],
            "trust": ["trust", "trustee", "beneficiary"],
            "partnership": ["partnership", "partner"],
            "smsf": ["self managed super", "smsf", "self-managed superannuation"],
        }

        for entity_type, keywords in entity_keywords.items():
            if any(kw in text_lower for kw in keywords):
                entity_types.append(entity_type)

        return entity_types if entity_types else ["all"]
