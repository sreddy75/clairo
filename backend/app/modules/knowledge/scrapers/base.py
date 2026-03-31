"""Base scraper class for knowledge base content sources.

Provides common functionality for all scrapers:
- HTTP client with rate limiting
- Retry logic with exponential backoff
- Content extraction and cleaning
- Progress tracking
"""

import asyncio
import logging
import random
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

logger = logging.getLogger(__name__)


@dataclass
class ScraperConfig:
    """Configuration for a scraper."""

    # Rate limiting
    requests_per_second: float = 1.0
    max_concurrent_requests: int = 3

    # Retry settings
    max_retries: int = 3
    retry_min_wait: float = 1.0
    retry_max_wait: float = 30.0

    # HTTP settings
    timeout: float = 30.0
    user_agent: str = (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    )

    # Additional headers to mimic a real browser
    # Note: Don't include Accept-Encoding as httpx handles this automatically
    default_headers: dict = field(
        default_factory=lambda: {
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-AU,en-GB;q=0.9,en;q=0.8",
            "DNT": "1",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Sec-CH-UA": '"Chromium";v="131", "Google Chrome";v="131", "Not_A Brand";v="24"',
            "Sec-CH-UA-Mobile": "?0",
            "Sec-CH-UA-Platform": '"macOS"',
            "Cache-Control": "max-age=0",
            "Priority": "u=0, i",
        }
    )

    # Content settings
    max_content_length: int = 5_000_000  # 5MB


@dataclass
class ScrapedContent:
    """Content extracted from a source.

    Represents a single piece of content ready for chunking and embedding.
    """

    # Identification
    source_url: str
    title: str | None = None

    # Content
    text: str = ""
    html: str | None = None

    # Classification
    source_type: str = "unknown"
    collection_namespace: str = "general"

    # Metadata
    effective_date: datetime | None = None
    expiry_date: datetime | None = None
    ruling_number: str | None = None

    # Applicability
    entity_types: list[str] = field(default_factory=list)
    industries: list[str] = field(default_factory=list)
    revenue_brackets: list[str] = field(default_factory=list)

    # Quality indicators
    confidence_level: str = "medium"
    is_superseded: bool = False
    superseded_by: str | None = None

    # Scraping metadata
    scraped_at: datetime = field(default_factory=lambda: datetime.now(tz=UTC))
    raw_metadata: dict = field(default_factory=dict)

    def to_chunk_payload(self, chunk_id: str, source_id: str, chunk_index: int) -> dict:
        """Convert to Qdrant payload format.

        Args:
            chunk_id: UUID for the chunk.
            source_id: UUID of the KnowledgeSource.
            chunk_index: Position in the source document.

        Returns:
            Dict suitable for Qdrant point payload.
        """
        return {
            "chunk_id": chunk_id,
            "source_id": source_id,
            "source_url": self.source_url,
            "title": self.title,
            "chunk_index": chunk_index,
            "source_type": self.source_type,
            "collection_namespace": self.collection_namespace,
            "entity_types": self.entity_types,
            "industries": self.industries,
            "revenue_brackets": self.revenue_brackets,
            "effective_date": self.effective_date.isoformat() if self.effective_date else None,
            "expiry_date": self.expiry_date.isoformat() if self.expiry_date else None,
            "ruling_number": self.ruling_number,
            "is_superseded": self.is_superseded,
            "superseded_by": self.superseded_by,
            "confidence_level": self.confidence_level,
            "scraped_at": self.scraped_at.isoformat(),
        }


class ScraperError(Exception):
    """Base exception for scraper errors."""

    pass


class RateLimitError(ScraperError):
    """Raised when rate limited by the source."""

    pass


class ContentError(ScraperError):
    """Raised when content extraction fails."""

    pass


class BaseScraper(ABC):
    """Abstract base class for content scrapers.

    Provides common functionality for HTTP requests, rate limiting,
    and content extraction. Subclasses must implement the abstract methods.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialize the scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific configuration from KnowledgeSource.
        """
        self.config = config or ScraperConfig()
        self.source_config = source_config or {}

        # Rate limiting
        self._request_interval = 1.0 / self.config.requests_per_second
        self._last_request_time = 0.0
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_requests)

        # Track last URL for Referer header chain
        self._last_url: str | None = None

        # HTTP client (created on demand)
        self._client: httpx.AsyncClient | None = None

    async def __aenter__(self) -> "BaseScraper":
        """Async context manager entry."""
        await self._ensure_client()
        return self

    async def __aexit__(self, *args: Any) -> None:
        """Async context manager exit."""
        await self.close()

    async def _ensure_client(self) -> httpx.AsyncClient:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            headers = {"User-Agent": self.config.user_agent}
            headers.update(self.config.default_headers)
            self._client = httpx.AsyncClient(
                timeout=self.config.timeout,
                headers=headers,
                follow_redirects=True,
                http2=True,
            )
        return self._client

    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

    # =========================================================================
    # Abstract Methods (must be implemented by subclasses)
    # =========================================================================

    @property
    @abstractmethod
    def source_type(self) -> str:
        """Return the source type identifier (e.g., 'ato_rss', 'ato_web')."""
        ...

    @property
    @abstractmethod
    def collection_name(self) -> str:
        """Return the target Qdrant collection name."""
        ...

    @abstractmethod
    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield URLs to scrape from this source.

        This method should discover all URLs that need to be scraped,
        typically from a feed, sitemap, or by crawling.

        Yields:
            URLs to scrape.
        """
        ...

    @abstractmethod
    async def extract_content(self, url: str, html: str) -> ScrapedContent | None:
        """Extract content from a scraped page.

        Args:
            url: The URL that was scraped.
            html: Raw HTML content.

        Returns:
            ScrapedContent object or None if content should be skipped.
        """
        ...

    # =========================================================================
    # Core Scraping Methods
    # =========================================================================

    async def scrape_all(self) -> AsyncIterator[ScrapedContent]:
        """Scrape all content from this source.

        Yields:
            ScrapedContent objects for each piece of content.
        """
        async for url in self.get_content_urls():
            try:
                content = await self.scrape_url(url)
                if content:
                    yield content
            except ScraperError as e:
                logger.warning(f"Failed to scrape {url}: {e}")
                continue

    async def scrape_url(self, url: str) -> ScrapedContent | None:
        """Scrape a single URL.

        Args:
            url: URL to scrape.

        Returns:
            ScrapedContent or None if extraction failed.
        """
        try:
            html = await self._fetch_url(url)
            if not html:
                return None

            content = await self.extract_content(url, html)
            return content

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            raise ScraperError(f"Failed to scrape {url}: {e}") from e

    # =========================================================================
    # HTTP Methods with Rate Limiting
    # =========================================================================

    async def _rate_limit(self) -> None:
        """Enforce rate limiting between requests."""
        now = asyncio.get_event_loop().time()
        elapsed = now - self._last_request_time
        if elapsed < self._request_interval:
            await asyncio.sleep(self._request_interval - elapsed)
        self._last_request_time = asyncio.get_event_loop().time()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=1, max=30),
        retry=retry_if_exception_type((httpx.TimeoutException, httpx.ConnectError)),
        reraise=True,
    )
    async def _fetch_url(self, url: str) -> str | None:
        """Fetch a URL with rate limiting and retries.

        Args:
            url: URL to fetch.

        Returns:
            HTML content or None if fetch failed.
        """
        async with self._semaphore:
            await self._rate_limit()
            # Add small random jitter to look more human
            await asyncio.sleep(random.uniform(0.2, 1.0))  # noqa: S311

            client = await self._ensure_client()

            # Build per-request headers with Referer chain
            request_headers: dict[str, str] = {}
            if self._last_url:
                request_headers["Referer"] = self._last_url

            try:
                response = await client.get(url, headers=request_headers)

                # Check for rate limiting
                if response.status_code == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    logger.warning(f"Rate limited, waiting {retry_after}s")
                    await asyncio.sleep(retry_after)
                    raise RateLimitError(f"Rate limited on {url}")

                response.raise_for_status()

                # Check content length
                content_length = int(response.headers.get("Content-Length", 0))
                if content_length > self.config.max_content_length:
                    logger.warning(f"Content too large: {url} ({content_length} bytes)")
                    return None

                self._last_url = url
                return response.text

            except httpx.HTTPStatusError as e:
                if e.response.status_code == 404:
                    logger.info(f"Page not found: {url}")
                    return None
                if e.response.status_code == 403:
                    logger.warning(f"Access forbidden (403): {url} - site may be blocking scrapers")
                    return None
                raise

    async def fetch_feed(self, url: str) -> str | None:
        """Fetch a feed (RSS/Atom) URL.

        Args:
            url: Feed URL.

        Returns:
            Feed content or None.
        """
        return await self._fetch_url(url)

    # =========================================================================
    # Content Extraction Helpers
    # =========================================================================

    def clean_html(self, html: str) -> BeautifulSoup:
        """Parse and clean HTML content.

        Removes scripts, styles, and navigation elements.

        Args:
            html: Raw HTML.

        Returns:
            BeautifulSoup object.
        """
        soup = BeautifulSoup(html, "lxml")

        # Remove non-content elements
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        # Remove hidden elements
        for tag in soup.find_all(attrs={"style": lambda v: v and "display:none" in v}):
            tag.decompose()

        return soup

    def extract_text(self, soup: BeautifulSoup, selector: str | None = None) -> str:
        """Extract text from BeautifulSoup object.

        Args:
            soup: BeautifulSoup object.
            selector: Optional CSS selector for content container.

        Returns:
            Extracted text.
        """
        if selector:
            element = soup.select_one(selector)
            if element:
                return element.get_text(separator="\n", strip=True)
            return ""

        # Try common content containers
        for container in ["main", "article", ".content", "#content", ".main-content"]:
            element = soup.select_one(container)
            if element:
                return element.get_text(separator="\n", strip=True)

        # Fallback to body
        body = soup.find("body")
        if body:
            return body.get_text(separator="\n", strip=True)

        return soup.get_text(separator="\n", strip=True)

    def extract_title(self, soup: BeautifulSoup) -> str | None:
        """Extract page title.

        Args:
            soup: BeautifulSoup object.

        Returns:
            Title string or None.
        """
        # Try og:title first
        og_title = soup.find("meta", property="og:title")
        if og_title and og_title.get("content"):
            return og_title["content"]

        # Try <title> tag
        title_tag = soup.find("title")
        if title_tag:
            return title_tag.get_text(strip=True)

        # Try h1
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)

        return None

    def make_absolute_url(self, base_url: str, relative_url: str) -> str:
        """Convert relative URL to absolute.

        Args:
            base_url: Base URL for resolution.
            relative_url: Potentially relative URL.

        Returns:
            Absolute URL.
        """
        if relative_url.startswith(("http://", "https://")):
            return relative_url
        return urljoin(base_url, relative_url)

    def get_domain(self, url: str) -> str:
        """Extract domain from URL.

        Args:
            url: Full URL.

        Returns:
            Domain string.
        """
        parsed = urlparse(url)
        return parsed.netloc
