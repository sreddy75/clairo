"""TPB and Treasury scraper for practitioner guidance and exposure drafts.

Scrapes content from two sources:

1. **Tax Practitioners Board (TPB)** -- tpb.gov.au information products.
   These are standard HTML pages covering practitioner registration,
   obligations, and guidance.

2. **Treasury exposure drafts** (placeholder) -- treasury.gov.au
   consultation documents.  Currently a stub awaiting implementation
   once Treasury publishes a stable content structure.

Both sources produce :class:`ScrapedContent` objects suitable for the
standard chunking pipeline.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import AsyncIterator

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)

# ============================================================================
# Constants
# ============================================================================

# TPB base URL
TPB_BASE_URL = "https://www.tpb.gov.au"

# Known TPB information product page paths.
# TPB restructured to flat slugs circa 2025 (old hierarchical paths return 404).
TPB_DEFAULT_PATHS: list[str] = [
    "/policy-and-guidance",
    "/tpb-information-products-topic",
    "/apply-register",
    "/tax-agent-registration",
    "/bas-agent-registration",
    "/code-professional-conduct",
    "/code-determination-background-and-context",
    "/qualifications-and-experience-tax-agents",
    "/know-your-obligations-3",
    "/failing-comply-your-obligations",
    "/guide-our-products",
]

# Treasury exposure drafts base URL (placeholder).
TREASURY_BASE_URL = "https://treasury.gov.au"

# Treasury consultation paths (placeholder -- these will need updating
# as Treasury publishes new drafts).
TREASURY_DEFAULT_PATHS: list[str] = [
    "/consultation/tax-consultations",
]

# Topic tags applicable to TPB content.
TPB_TOPIC_TAGS: list[str] = [
    "tpb",
    "tax_practitioner",
    "registration",
    "compliance",
]

# Topic tags for Treasury content.
TREASURY_TOPIC_TAGS: list[str] = [
    "treasury",
    "exposure_draft",
    "consultation",
]


class TPBTreasuryScraper(BaseScraper):
    """Scraper for TPB information products and Treasury exposure drafts.

    A simpler scraper that fetches standard HTML pages from tpb.gov.au
    and (optionally) Treasury consultation pages.

    Configuration via ``source_config``:
        - ``source``: One of ``"tpb"``, ``"treasury"``, or ``"both"``
          (default: ``"tpb"``).
        - ``tpb_paths``: Custom list of TPB page paths to scrape
          (default: :data:`TPB_DEFAULT_PATHS`).
        - ``treasury_paths``: Custom list of Treasury page paths to
          scrape (default: :data:`TREASURY_DEFAULT_PATHS`).
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialise the TPB/Treasury scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific configuration.
        """
        super().__init__(config or ScraperConfig(), source_config)

        self._source: str = self.source_config.get("source", "tpb")
        self._tpb_paths: list[str] = self.source_config.get("tpb_paths", TPB_DEFAULT_PATHS)
        self._treasury_paths: list[str] = self.source_config.get(
            "treasury_paths", TREASURY_DEFAULT_PATHS
        )

    # ------------------------------------------------------------------
    # Abstract property implementations
    # ------------------------------------------------------------------

    @property
    def source_type(self) -> str:
        """Return the source type identifier."""
        return "tpb"

    @property
    def collection_name(self) -> str:
        """Return the target collection name."""
        return "compliance_knowledge"

    # ------------------------------------------------------------------
    # URL Discovery
    # ------------------------------------------------------------------

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield URLs for TPB and/or Treasury pages.

        Yields:
            Full URLs for each configured page path.
        """
        if self._source in ("tpb", "both"):
            for path in self._tpb_paths:
                url = f"{TPB_BASE_URL}{path}" if path.startswith("/") else path
                yield url

        if self._source in ("treasury", "both"):
            for path in self._treasury_paths:
                url = f"{TREASURY_BASE_URL}{path}" if path.startswith("/") else path
                yield url

    # ------------------------------------------------------------------
    # Content Extraction
    # ------------------------------------------------------------------

    async def extract_content(self, url: str, html: str) -> ScrapedContent | None:
        """Extract content from a TPB or Treasury HTML page.

        Standard HTML page scraping: parse the page, extract the main
        content area, and return a ScrapedContent with appropriate
        natural key and metadata.

        Args:
            url: The page URL.
            html: Raw HTML content.

        Returns:
            ScrapedContent or None if the page has insufficient content.
        """
        soup = self.clean_html(html)
        title = self.extract_title(soup)
        text = self.extract_text(soup)

        if not text or len(text) < 50:
            logger.debug("Insufficient content for %s", url)
            return None

        # Determine whether this is a TPB or Treasury page
        is_tpb = TPB_BASE_URL in url
        source_label = "tpb" if is_tpb else "treasury"

        # Build natural key from URL hash
        url_hash = hashlib.sha256(url.encode()).hexdigest()[:16]
        natural_key = f"{source_label}:{url_hash}"

        # Compute document hash for change detection
        document_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        # Select appropriate topic tags
        topic_tags = list(TPB_TOPIC_TAGS if is_tpb else TREASURY_TOPIC_TAGS)

        # Try to extract additional topic tags from the page content
        content_tags = self._extract_content_tags(text)
        for tag in content_tags:
            if tag not in topic_tags:
                topic_tags.append(tag)

        return ScrapedContent(
            source_url=url,
            title=title or f"{source_label.upper()} - {url}",
            text=text,
            html=str(soup),
            source_type=source_label,
            collection_namespace=self.collection_name,
            confidence_level="medium",
            raw_metadata={
                "natural_key": natural_key,
                "document_hash": document_hash,
                "topic_tags": topic_tags,
            },
        )

    # ------------------------------------------------------------------
    # Content tag extraction
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_content_tags(text: str) -> list[str]:
        """Extract additional topic tags from page content.

        Checks for common practitioner-related terms and maps them
        to tags.

        Args:
            text: Page text.

        Returns:
            List of additional topic tags.
        """
        text_lower = text[:3000].lower()
        tags: list[str] = []

        tag_keywords: dict[str, list[str]] = {
            "bas_agent": ["bas agent", "bas service"],
            "tax_agent": ["tax agent", "tax agent service"],
            "code_of_conduct": [
                "code of professional conduct",
                "code of conduct",
            ],
            "cpe": [
                "continuing professional education",
                "cpe",
                "professional development",
            ],
            "registration": ["registration", "register", "renew"],
            "pii": [
                "professional indemnity",
                "indemnity insurance",
                "pii",
            ],
            "sanctions": ["sanction", "suspension", "termination"],
            "gst": ["gst", "goods and services tax"],
            "income_tax": ["income tax"],
        }

        for tag, keywords in tag_keywords.items():
            if any(kw in text_lower for kw in keywords):
                tags.append(tag)

        return tags
