"""ATO Public API scraper for PDF content guides.

Fetches comprehensive PDF guides from ATO's public API endpoints.
These PDFs contain detailed, structured content that's ideal for
knowledge base ingestion.

Endpoint Pattern:
    https://www.ato.gov.au/api/public/content/{content-id}

The content IDs can be found by inspecting the ATO website's
"Print whole section" functionality.
"""

import logging
import re
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import fitz  # PyMuPDF

from app.modules.knowledge.scrapers.base import (
    BaseScraper,
    ScrapedContent,
    ScraperConfig,
)

logger = logging.getLogger(__name__)


# Known ATO content IDs for comprehensive guides
ATO_CONTENT_IDS = {
    # BAS and GST
    "bas_guide": "0-9fc804ad-a043-4a35-b540-16b71d9ca9bf",
    "gst_guide": "0-1e92db95-a75c-4f4e-a3d4-39f43b1a3b25",
    "gst_registration": "0-b6bb7e3e-5a05-4f5c-8c85-7d55a95e48b3",
    # PAYG
    "payg_withholding": "0-0301fa63-0661-45f7-b2f3-857b59686672",
    "payg_instalments": "0-7a8b1c2d-3e4f-5a6b-7c8d-9e0f1a2b3c4d",
    # FBT
    "fbt_guide": "0-4fb0f16e-89f1-4068-aec9-c8acb1befc04",
    # Business
    "starting_business": "0-b39e5690-1e2a-4555-b42d-8805d5ea5a7e",
    "prepare_lodge": "0-bb1ec3d7-b642-4f98-9ca3-c66f79ecc38d",
    "due_dates": "0-e1b124df-c349-4556-93f4-68564fe5aab6",
    # Super
    "super_employers": "0-c3d4e5f6-7a8b-9c0d-1e2f-3a4b5c6d7e8f",
}


# Namespace mapping based on content type
CONTENT_NAMESPACE_MAP = {
    "bas": "compliance_knowledge",
    "gst": "compliance_knowledge",
    "payg": "compliance_knowledge",
    "fbt": "compliance_knowledge",
    "super": "compliance_knowledge",
    "starting": "business_fundamentals",
    "prepare": "compliance_knowledge",
    "due_dates": "compliance_knowledge",
}


class ATOAPIScraper(BaseScraper):
    """Scraper for ATO Public API PDF content.

    Fetches comprehensive PDF guides from the ATO API and extracts
    text content for the knowledge base.
    """

    def __init__(
        self,
        config: ScraperConfig | None = None,
        source_config: dict | None = None,
    ) -> None:
        """Initialize the ATO API scraper.

        Args:
            config: Scraper configuration.
            source_config: Source-specific config with:
                - content_ids: List of content ID keys or raw IDs
                - base_url: API base URL (default: https://www.ato.gov.au/api/public/content)
        """
        super().__init__(config, source_config)

        self._base_url = (
            source_config.get("base_url", "https://www.ato.gov.au/api/public/content")
            if source_config
            else "https://www.ato.gov.au/api/public/content"
        )

        # Get content IDs to fetch
        content_id_keys = source_config.get("content_ids", []) if source_config else []

        # Resolve content IDs (support both keys and raw IDs)
        self._content_ids = []
        for cid in content_id_keys:
            if cid in ATO_CONTENT_IDS:
                self._content_ids.append((cid, ATO_CONTENT_IDS[cid]))
            else:
                # Assume it's a raw content ID
                self._content_ids.append((cid, cid))

        # If no content IDs specified, use defaults based on source type
        if not self._content_ids:
            default_ids = ["bas_guide", "gst_guide", "payg_withholding"]
            self._content_ids = [(k, ATO_CONTENT_IDS[k]) for k in default_ids]

    @property
    def source_type(self) -> str:
        return "ato_api"

    @property
    def collection_name(self) -> str:
        return "compliance_knowledge"

    async def get_content_urls(self) -> AsyncIterator[str]:
        """Yield API URLs for configured content IDs.

        Yields:
            Full API URLs for each content ID.
        """
        for name, content_id in self._content_ids:
            url = f"{self._base_url}/{content_id}"
            logger.info(f"Queuing ATO API content: {name} ({content_id})")
            yield url

    async def _fetch_pdf(self, url: str) -> bytes | None:
        """Fetch PDF content from URL.

        Args:
            url: URL to fetch.

        Returns:
            PDF bytes or None if fetch failed.
        """
        async with self._semaphore:
            await self._rate_limit()

            client = await self._ensure_client()

            try:
                response = await client.get(url)
                response.raise_for_status()

                content_type = response.headers.get("content-type", "")
                if "pdf" not in content_type.lower():
                    logger.warning(f"Unexpected content type: {content_type} for {url}")
                    return None

                return response.content

            except Exception as e:
                logger.error(f"Error fetching PDF from {url}: {e}")
                return None

    async def scrape_url(self, url: str) -> ScrapedContent | None:
        """Scrape a single PDF URL.

        Overrides base method to handle PDF content.

        Args:
            url: URL to scrape.

        Returns:
            ScrapedContent or None if extraction failed.
        """
        try:
            pdf_bytes = await self._fetch_pdf(url)
            if not pdf_bytes:
                return None

            content = await self.extract_content(url, pdf_bytes)
            return content

        except Exception as e:
            logger.error(f"Error scraping {url}: {e}")
            return None

    async def extract_content(self, url: str, pdf_bytes: bytes | str) -> ScrapedContent | None:
        """Extract content from PDF.

        Args:
            url: The URL that was scraped.
            pdf_bytes: PDF content as bytes.

        Returns:
            ScrapedContent object or None if content should be skipped.
        """
        # Handle if passed as string (from base class interface)
        if isinstance(pdf_bytes, str):
            pdf_bytes = pdf_bytes.encode("latin-1")

        try:
            # Parse PDF with PyMuPDF
            pdf_document = fitz.open(stream=pdf_bytes, filetype="pdf")

            # Extract metadata
            metadata = pdf_document.metadata
            title = metadata.get("title") or self._extract_title_from_url(url)

            # Extract text from all pages
            text_parts = []
            for page_num in range(len(pdf_document)):
                page = pdf_document[page_num]
                text = page.get_text("text")
                if text.strip():
                    text_parts.append(text)

            pdf_document.close()

            full_text = "\n\n".join(text_parts)

            # Clean up text
            full_text = self._clean_pdf_text(full_text)

            if len(full_text) < 100:
                logger.warning(f"Insufficient content extracted from {url}")
                return None

            # Determine namespace and source type
            namespace = self._determine_namespace(url, title, full_text)
            source_type = self._determine_source_type(url, title)

            # Extract entity types
            entity_types = self._extract_entity_types(full_text)

            logger.info(f"Extracted {len(full_text)} chars from PDF: {title or url}")

            return ScrapedContent(
                source_url=url,
                title=title,
                text=full_text,
                html=None,
                source_type=source_type,
                collection_namespace=namespace,
                effective_date=datetime.now(tz=UTC),
                entity_types=entity_types,
                confidence_level="high",  # PDFs are authoritative content
            )

        except Exception as e:
            logger.error(f"Error extracting PDF content from {url}: {e}")
            return None

    def _extract_title_from_url(self, url: str) -> str:
        """Extract a title from the URL or content ID.

        Args:
            url: Content URL.

        Returns:
            Title string.
        """
        # Try to find matching content ID name
        content_id = url.split("/")[-1]
        for name, cid in ATO_CONTENT_IDS.items():
            if cid == content_id:
                return name.replace("_", " ").title()

        return f"ATO Guide ({content_id[:8]}...)"

    def _clean_pdf_text(self, text: str) -> str:
        """Clean extracted PDF text.

        Args:
            text: Raw PDF text.

        Returns:
            Cleaned text.
        """
        # Remove excessive whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+", " ", text)

        # Remove page numbers and headers/footers
        text = re.sub(r"\n\d+\s*\n", "\n", text)
        text = re.sub(r"Page \d+ of \d+", "", text)
        text = re.sub(r"Australian Taxation Office\s*\n", "", text)

        # Remove common PDF artifacts
        text = re.sub(r"\uf0b7", "•", text)  # Bullet points
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", text)  # Control chars

        return text.strip()

    def _determine_namespace(self, url: str, title: str | None, text: str) -> str:
        """Determine the collection namespace.

        Args:
            url: Content URL.
            title: Content title.
            text: Content text.

        Returns:
            Namespace string.
        """
        combined = f"{url} {title or ''} {text[:1000]}".lower()

        # Check for specific topics
        if any(kw in combined for kw in ["gst", "goods and services tax"]):
            return "compliance_knowledge"
        if any(kw in combined for kw in ["bas", "business activity statement"]):
            return "compliance_knowledge"
        if any(kw in combined for kw in ["payg", "withholding", "pay as you go"]):
            return "compliance_knowledge"
        if any(kw in combined for kw in ["fbt", "fringe benefit"]):
            return "compliance_knowledge"
        if any(kw in combined for kw in ["super", "superannuation"]):
            return "compliance_knowledge"
        if any(kw in combined for kw in ["starting", "register", "abn"]):
            return "business_fundamentals"

        return "compliance_knowledge"

    def _determine_source_type(self, url: str, title: str | None) -> str:
        """Determine the source type for classification.

        Args:
            url: Content URL.
            title: Content title.

        Returns:
            Source type string.
        """
        combined = f"{url} {title or ''}".lower()

        if "guide" in combined:
            return "ato_guide"
        if "ruling" in combined:
            return "ato_ruling"
        if "form" in combined:
            return "ato_form"

        return "ato_guide"

    def _extract_entity_types(self, text: str) -> list[str]:
        """Extract applicable entity types from content.

        Args:
            text: Content text.

        Returns:
            List of entity types.
        """
        text_lower = text.lower()
        entity_types = []

        entity_keywords = {
            "sole_trader": ["sole trader", "individual business"],
            "company": ["company", "companies", "corporation", "pty ltd"],
            "trust": ["trust", "trustee", "beneficiary"],
            "partnership": ["partnership", "partner"],
            "smsf": ["self managed super", "smsf", "self-managed superannuation"],
        }

        for entity_type, keywords in entity_keywords.items():
            if any(kw in text_lower for kw in keywords):
                entity_types.append(entity_type)

        return entity_types if entity_types else ["all"]
