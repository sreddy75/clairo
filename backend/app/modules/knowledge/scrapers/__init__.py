"""Content scrapers for knowledge base ingestion.

This module provides scrapers for various content sources:
- ATO API (PDF guides via public API)
- ATO Legal Database (rulings, determinations, guidelines)
- ATO RSS feeds (tax rulings, news)
- ATO website pages
- Legislation.gov.au (Australian tax legislation)
- Case law (Open Australian Legal Corpus + Federal Court RSS)
- TPB / Treasury (practitioner guidance + exposure drafts)
- AustLII legislation
- Business.gov.au guides

Circuit breaker support:
- ScraperCircuitBreaker: DB-backed circuit breaker to avoid hammering failing sites
- CircuitOpenError: Raised when a circuit is open and requests are blocked
"""

from app.modules.knowledge.scrapers.ato_api import ATOAPIScraper
from app.modules.knowledge.scrapers.ato_legal_db import ATOLegalDatabaseScraper
from app.modules.knowledge.scrapers.ato_rss import ATORSSScraper
from app.modules.knowledge.scrapers.ato_web import ATOWebScraper
from app.modules.knowledge.scrapers.base import BaseScraper, ScrapedContent, ScraperConfig
from app.modules.knowledge.scrapers.case_law import CaseLawScraper
from app.modules.knowledge.scrapers.circuit_breaker import (
    CircuitOpenError,
    ScraperCircuitBreaker,
)
from app.modules.knowledge.scrapers.legislation_gov import LegislationGovScraper
from app.modules.knowledge.scrapers.tpb_treasury import TPBTreasuryScraper

__all__ = [
    "ATOAPIScraper",
    "ATOLegalDatabaseScraper",
    "ATORSSScraper",
    "ATOWebScraper",
    "BaseScraper",
    "CaseLawScraper",
    "CircuitOpenError",
    "LegislationGovScraper",
    "ScrapedContent",
    "ScraperCircuitBreaker",
    "ScraperConfig",
    "TPBTreasuryScraper",
]
