#!/usr/bin/env python3
"""
Seed Knowledge Base Sources

This script populates all 6 knowledge collections with relevant sources
for Australian accounting/BAS context. Run this once to set up initial
knowledge sources, then use the Admin UI for future modifications.

Usage:
    # From the backend directory:
    cd backend
    uv run python ../scripts/seed_knowledge_sources.py

Requirements:
    - Backend API running on localhost:8000
    - CLERK_SECRET_KEY environment variable (to get a super admin token)
    - Or pass a token directly: python seed_knowledge_sources.py --token <JWT>
"""

import argparse
import asyncio
import os
import sys
from typing import Any

import httpx

# API Configuration
API_BASE = os.getenv("API_BASE", "http://localhost:8000")
ADMIN_ENDPOINT = f"{API_BASE}/api/v1/admin/knowledge"


# =============================================================================
# Knowledge Sources Configuration
# =============================================================================

KNOWLEDGE_SOURCES: list[dict[str, Any]] = [
    # =========================================================================
    # COMPLIANCE KNOWLEDGE - ATO rules, legislation, tax compliance guidance
    # =========================================================================
    {
        "name": "ATO BAS Guides",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas",
                "/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/completing-your-bas",
                "/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas/bas-due-dates",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO GST Guide",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/gst-excise-and-indirect-taxes/gst",
                "/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/how-gst-works",
                "/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/claiming-gst-credits",
                "/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/issuing-tax-invoices",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO PAYG Withholding",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding",
                "/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding/payg-withholding-from-salary-and-wages",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO PAYG Instalments",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/paying-the-ato/payg-instalments",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/preparing-lodging-and-paying/paying-the-ato/payg-instalments",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Tax Rulings RSS",
        "source_type": "ato_rss",
        "base_url": "https://www.ato.gov.au/rss/rulings.xml",
        "collection_name": "compliance_knowledge",
        "scrape_config": {
            "feeds": ["rulings"],
        },
        "is_active": True,
    },
    # =========================================================================
    # STRATEGIC ADVISORY - Tax optimization, entity structuring
    # =========================================================================
    {
        "name": "ATO Small Business Tax",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/small-business",
        "collection_name": "strategic_advisory",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/income-deductions-and-concessions/small-business",
                "/businesses-and-organisations/income-deductions-and-concessions/small-business/small-business-entity-concessions",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Business Structures",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business",
        "collection_name": "strategic_advisory",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/business-structures",
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/business-structures/sole-trader",
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/business-structures/company",
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/business-structures/partnership",
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/business-structures/trust",
            ],
            "max_depth": 1,
        },
        "is_active": True,
    },
    # =========================================================================
    # INDUSTRY KNOWLEDGE - Industry-specific deductions, benchmarks
    # =========================================================================
    {
        "name": "ATO Industry Benchmarks",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/benchmarks",
        "collection_name": "industry_knowledge",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/income-deductions-and-concessions/benchmarks",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Occupation Guides",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim",
        "collection_name": "industry_knowledge",
        "scrape_config": {
            "urls": [
                "/individuals-and-families/income-deductions-offsets-and-records/deductions-you-can-claim/occupation-and-industry-specific-guides",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    # =========================================================================
    # BUSINESS FUNDAMENTALS - Starting business, ABN, planning
    # =========================================================================
    {
        "name": "ATO Starting Business",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business",
        "collection_name": "business_fundamentals",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business",
                "/businesses-and-organisations/starting-and-running-your-business/starting-your-own-business/key-steps-for-starting-a-business",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO ABN Registration",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/registering-for-tax/abn-registration",
        "collection_name": "business_fundamentals",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/registering-for-tax/abn-registration",
                "/businesses-and-organisations/registering-for-tax/abn-registration/apply-for-an-abn",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    # =========================================================================
    # FINANCIAL MANAGEMENT - Cash flow, debtor management, record keeping
    # =========================================================================
    {
        "name": "ATO Record Keeping",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/record-keeping-for-business",
        "collection_name": "financial_management",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/income-deductions-and-concessions/record-keeping-for-business",
                "/businesses-and-organisations/income-deductions-and-concessions/record-keeping-for-business/how-long-to-keep-your-records",
                "/businesses-and-organisations/income-deductions-and-concessions/record-keeping-for-business/electronic-record-keeping",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Deductions Guide",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business",
        "collection_name": "financial_management",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business",
                "/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/deductions",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    # =========================================================================
    # PEOPLE OPERATIONS - Hiring, employment, payroll, superannuation
    # =========================================================================
    {
        "name": "ATO Hiring Workers",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers",
        "collection_name": "people_operations",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/hiring-and-paying-your-workers",
                "/businesses-and-organisations/hiring-and-paying-your-workers/employee-or-contractor",
                "/businesses-and-organisations/hiring-and-paying-your-workers/working-out-what-to-pay-your-workers",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Super for Employers",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/super-for-employers",
        "collection_name": "people_operations",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/super-for-employers",
                "/businesses-and-organisations/super-for-employers/paying-super-contributions",
                "/businesses-and-organisations/super-for-employers/setting-up-super-for-your-business",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
    {
        "name": "ATO Single Touch Payroll",
        "source_type": "ato_web",
        "base_url": "https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/single-touch-payroll",
        "collection_name": "people_operations",
        "scrape_config": {
            "urls": [
                "/businesses-and-organisations/hiring-and-paying-your-workers/single-touch-payroll",
            ],
            "max_depth": 2,
        },
        "is_active": True,
    },
]


# =============================================================================
# API Functions
# =============================================================================


async def get_existing_sources(client: httpx.AsyncClient, token: str) -> list[dict]:
    """Get all existing knowledge sources."""
    response = await client.get(
        f"{ADMIN_ENDPOINT}/sources",
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


async def create_source(
    client: httpx.AsyncClient, token: str, source: dict[str, Any]
) -> dict:
    """Create a new knowledge source."""
    response = await client.post(
        f"{ADMIN_ENDPOINT}/sources",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=source,
    )
    response.raise_for_status()
    return response.json()


async def trigger_ingestion(
    client: httpx.AsyncClient, token: str, source_id: str
) -> dict:
    """Trigger ingestion for a source."""
    response = await client.post(
        f"{ADMIN_ENDPOINT}/sources/{source_id}/ingest",
        headers={"Authorization": f"Bearer {token}"},
    )
    response.raise_for_status()
    return response.json()


# =============================================================================
# Main Seed Function
# =============================================================================


async def seed_knowledge_sources(token: str, trigger_ingest: bool = True) -> None:
    """Seed all knowledge sources.

    Args:
        token: JWT authentication token.
        trigger_ingest: Whether to trigger ingestion after creating sources.
    """
    async with httpx.AsyncClient(timeout=60.0) as client:
        # Get existing sources to avoid duplicates
        print("Fetching existing sources...")
        try:
            existing = await get_existing_sources(client, token)
            existing_names = {s["name"] for s in existing}
            print(f"Found {len(existing)} existing sources")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                print("ERROR: Invalid or expired token. Please provide a valid JWT.")
                sys.exit(1)
            elif e.response.status_code == 403:
                print("ERROR: Token does not have super_admin role.")
                sys.exit(1)
            raise

        # Create new sources
        created_sources = []
        skipped = 0

        for source in KNOWLEDGE_SOURCES:
            if source["name"] in existing_names:
                print(f"  SKIP: {source['name']} (already exists)")
                skipped += 1
                continue

            try:
                print(f"  Creating: {source['name']}...")
                result = await create_source(client, token, source)
                created_sources.append(result)
                print(f"    -> Created: {result['id']}")
            except httpx.HTTPStatusError as e:
                print(f"    -> ERROR: {e.response.status_code} - {e.response.text}")
                continue

        print(f"\nCreated {len(created_sources)} sources, skipped {skipped}")

        # Trigger ingestion for all new sources
        if trigger_ingest and created_sources:
            print("\nTriggering ingestion jobs...")
            jobs_started = 0

            for source in created_sources:
                try:
                    print(f"  Starting ingestion: {source['name']}...")
                    job = await trigger_ingestion(client, token, source["id"])
                    print(f"    -> Job ID: {job['id']}")
                    jobs_started += 1
                except httpx.HTTPStatusError as e:
                    print(f"    -> ERROR: {e.response.status_code} - {e.response.text}")

            print(f"\nStarted {jobs_started} ingestion jobs")
            print("\nMonitor progress in the Admin UI -> Jobs tab")

        print("\n" + "=" * 60)
        print("SEED COMPLETE")
        print("=" * 60)
        print(f"  Sources created: {len(created_sources)}")
        print(f"  Sources skipped: {skipped}")
        if trigger_ingest:
            print(f"  Ingestion jobs: {len(created_sources)}")
        print("\nVisit http://localhost:3000/admin/knowledge to monitor progress")


# =============================================================================
# Entry Point
# =============================================================================


def main():
    parser = argparse.ArgumentParser(description="Seed knowledge base sources")
    parser.add_argument(
        "--token",
        help="JWT token for authentication (or set via stdin)",
    )
    parser.add_argument(
        "--no-ingest",
        action="store_true",
        help="Only create sources, don't trigger ingestion",
    )
    parser.add_argument(
        "--api-base",
        default="http://localhost:8000",
        help="API base URL (default: http://localhost:8000)",
    )
    args = parser.parse_args()

    global API_BASE, ADMIN_ENDPOINT
    API_BASE = args.api_base
    ADMIN_ENDPOINT = f"{API_BASE}/api/v1/admin/knowledge"

    # Get token
    token = args.token
    if not token:
        print(
            "Enter your JWT token (from browser dev tools -> Network -> Authorization header):"
        )
        print("Or press Ctrl+C to cancel")
        try:
            token = input().strip()
            # Remove "Bearer " prefix if included
            if token.startswith("Bearer "):
                token = token[7:]
        except KeyboardInterrupt:
            print("\nCancelled")
            sys.exit(0)

    if not token:
        print("ERROR: No token provided")
        sys.exit(1)

    # Run the seeder
    asyncio.run(seed_knowledge_sources(token, trigger_ingest=not args.no_ingest))


if __name__ == "__main__":
    main()
