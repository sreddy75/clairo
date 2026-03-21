# Clairo Knowledge Base - Data Sources Strategy

## Executive Summary

This document outlines a comprehensive multi-channel approach to building a high-quality knowledge base for Australian tax compliance. The current web scraping approach is insufficient because the ATO website uses JavaScript rendering that BeautifulSoup cannot capture, resulting in generic navigation text instead of actual compliance content.

## Problem Statement

Current issues with website scraping:
- ATO website uses JavaScript to render content dynamically
- BeautifulSoup only captures static HTML (navigation menus, headers)
- Search results return low relevance scores (0.49-0.56)
- Missing specific details like "$75,000 GST threshold"
- Content lacks the depth needed for accurate AI responses

## Recommended Data Sources

### 1. ATO Public Content API (HIGH PRIORITY)

The ATO has internal API endpoints that serve full page content in a structured format.

**Endpoint Pattern:**
```
https://www.ato.gov.au/api/public/content/{content-id}
```

**Key Content IDs Discovered:**

| Content | URL |
|---------|-----|
| GST Complete Guide | `/api/public/content/0-1e92db95-a75c-4f4e-a3d4-39f43b1a3b25` |
| BAS Complete Guide | `/api/public/content/0-9fc804ad-a043-4a35-b540-16b71d9ca9bf` |
| PAYG Withholding | `/api/public/content/0-0301fa63-0661-45f7-b2f3-857b59686672` |
| FBT Rates & Thresholds | `/api/public/content/0-4fb0f16e-89f1-4068-aec9-c8acb1befc04` |
| Due Dates by Obligation | `/api/public/content/0-e1b124df-c349-4556-93f4-68564fe5aab6` |
| Starting/Registering Business | `/api/public/content/0-b39e5690-1e2a-4555-b42d-8805d5ea5a7e` |
| Prepare and Lodge | `/api/public/content/0-bb1ec3d7-b642-4f98-9ca3-c66f79ecc38d` |

**Implementation:** Create a new scraper type `ato_api` that fetches these endpoints directly.

---

### 2. ATO RSS Feeds (HIGH PRIORITY)

Official XML feeds providing structured access to rulings and updates.

**Legal Database Feeds** (at `ato.gov.au/law/view/rss/`):

| Feed | URL | Content |
|------|-----|---------|
| All Rulings | `/law/view/rss?fileid=pbr_all.rss` | All public rulings |
| GST Rulings | `/law/view/rss?fileid=pbr_gst.rss` | GST and sales tax |
| Taxation Rulings | `/law/view/rss?fileid=pbr_tax.rss` | Income tax, CGT, misc |
| Super Rulings | `/law/view/rss?fileid=pbr_super.rss` | Superannuation |
| Excise Rulings | `/law/view/rss?fileid=pbr_excise.rss` | Excise, fuel tax |
| Class/Product Rulings | `/law/view/rss?fileid=pbr_class_product.rss` | Class rulings |
| Interpretative Decisions | `/law/view/rss?fileid=ato_id.rss` | ATO IDs |
| Taxpayer Alerts | `/law/view/rss?fileid=ato_tpa.rss` | Alerts |
| Practice Statements | `/law/view/rss?fileid=ato_laps.rss` | LAPS |

**News Feeds** (at `ato.gov.au/rss/`):

| Feed | URL |
|------|-----|
| All New Information | `/rss/all-new-information.xml` |
| Businesses | `/rss/businesses-and-organisations.xml` |
| Tax Professionals | `/rss/tax-professionals.xml` |
| Forms & Instructions | `/rss/forms-and-instructions.xml` |
| Tax Rates & Codes | `/rss/tax-rates-and-codes.xml` |

**Implementation:** Create scraper type `ato_rss` that:
1. Parses RSS XML feeds
2. Follows links to full ruling documents
3. Extracts complete ruling text

---

### 3. ATO PDF Publications (MEDIUM PRIORITY)

Comprehensive downloadable guides with detailed compliance information.

**Key PDFs:**

| Document | URL |
|----------|-----|
| FBT Guide for Employers | `ato.gov.au/law/view/pdf/sos/fbtgemp20200129.pdf` |
| Super Guarantee Compliance | `ato.gov.au/law/view/pdf?DocId=AFS/SGcompliance/00001` |
| SG Employer Obligations Course | `ato.gov.au/misc/downloads/pdf/qc58510.pdf` |
| GST for Small Business | `ato.gov.au/misc/downloads/pdf/qc59733.pdf` |
| Monthly Tax Table | `/api/public/content/5c8c64b28f5f41659fee1ba9c04d81d0` |
| Withholding Declaration | `/api/public/content/fbcafb1f-944b-45d1-bf46-9376da50282c` |

**Third-Party Resources:**
- Lawpath GST & BAS Guide: `assets.lawpath.com/pdfs/2025-ebooks/A-Guide-to-GST-and-BAS-in-Australia.pdf`

**Implementation:**
- Add PDF parsing capability using PyMuPDF or pdfplumber
- Extract text, tables, and structure
- Chunk appropriately for vector storage

---

### 4. AustLII Database (MEDIUM PRIORITY)

Contains comprehensive ATO rulings dating back to 1980s, updated weekly from ATO data feeds.

**Database Categories:**
- GST Rulings (ATOGSTR)
- Taxation Rulings (ATOTR)
- Taxation Determinations (ATOTD)
- Superannuation Rulings
- Class Rulings (ATOCR)
- Product Rulings (ATOPR)

**Access:**
- Web scraping at `austlii.edu.au/au/other/rulings/ato/`
- Updated weekly from ATO
- Includes hyperlinks between related rulings

**Limitations:**
- No public bulk download API
- Copyright restrictions on markup reproduction
- Requires web scraping with proper attribution

---

### 5. Headless Browser Scraping (MEDIUM PRIORITY)

For JavaScript-rendered content that can't be accessed via API.

**Tool:** Playwright (Python)

**Use Cases:**
- ATO pages without API endpoints
- Interactive calculators content
- Dynamic form instructions

**Implementation:**
```python
from playwright.sync_api import sync_playwright

def scrape_js_content(url):
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle")
        content = page.content()
        browser.close()
        return content
```

---

### 6. Federal Register of Legislation (LOW PRIORITY)

Authoritative source for Commonwealth legislation.

**URL:** `legislation.gov.au`

**Relevant Acts:**
- A New Tax System (Goods and Services Tax) Act 1999
- Income Tax Assessment Act 1997
- Superannuation Guarantee (Administration) Act 1992
- Fringe Benefits Tax Assessment Act 1986
- Taxation Administration Act 1953

**Limitations:**
- No public API found
- Would require web scraping
- Content is highly technical/legal

---

## Content Areas to Cover

### Core BAS Topics
1. **GST (Goods and Services Tax)**
   - Registration threshold ($75,000 / $150,000 for NFP)
   - When to register
   - GST-free vs taxable supplies
   - Input tax credits
   - Simpler BAS reporting

2. **PAYG Withholding**
   - Tax tables and calculation
   - Employer obligations
   - Reporting via STP
   - BAS labels (W1, W2)

3. **PAYG Instalments**
   - Who pays
   - Calculation methods
   - Varying instalments

4. **Superannuation Guarantee**
   - Current rate (11.5% from July 2024, 12% from July 2025)
   - Ordinary time earnings
   - Due dates (quarterly)
   - Super guarantee charge

5. **Fringe Benefits Tax**
   - FBT year (April-March)
   - Rate (47%)
   - Gross-up rates
   - Exemptions
   - Reporting requirements

### Supporting Topics
6. **Single Touch Payroll (STP)**
   - Phase 2 requirements
   - Reporting obligations
   - Software compliance

7. **Due Dates & Lodgement**
   - BAS due dates (quarterly/monthly)
   - FBT return due dates
   - Super payment deadlines

8. **Small Business Concessions**
   - Simplified depreciation
   - Instant asset write-off
   - Simpler BAS

---

## Implementation Plan

### Phase 1: ATO API Integration (Week 1-2)
1. Create new scraper type: `ato_api`
2. Map all available content IDs via sitemap
3. Implement content extraction and chunking
4. Ingest core GST, BAS, PAYG content

### Phase 2: RSS Feed Integration (Week 2-3)
1. Create new scraper type: `ato_rss_legal`
2. Parse RSS feeds for rulings
3. Follow links and extract full ruling text
4. Set up scheduled ingestion for updates

### Phase 3: PDF Ingestion (Week 3-4)
1. Add PDF parsing library (PyMuPDF/pdfplumber)
2. Create new scraper type: `ato_pdf`
3. Ingest key PDF publications
4. Handle tables and structured content

### Phase 4: Headless Browser (Week 4-5)
1. Add Playwright dependency
2. Create new scraper type: `ato_playwright`
3. Identify pages requiring JS rendering
4. Implement rate-limited scraping

### Phase 5: AustLII Integration (Week 5-6)
1. Create new scraper type: `austlii`
2. Scrape ruling categories systematically
3. Set up weekly update schedule
4. Maintain ruling relationships

---

## Technical Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Knowledge Ingestion Pipeline              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   ATO API    │  │  ATO RSS     │  │   ATO PDF    │       │
│  │   Scraper    │  │  Scraper     │  │   Parser     │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │              │
│  ┌──────┴───────┐  ┌──────┴───────┐  ┌──────┴───────┐       │
│  │  Playwright  │  │   AustLII   │  │  Legislation │       │
│  │   Scraper    │  │   Scraper    │  │   Scraper    │       │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘       │
│         │                  │                  │              │
│         └──────────────────┼──────────────────┘              │
│                            ▼                                 │
│                  ┌─────────────────┐                        │
│                  │  Content        │                        │
│                  │  Processor      │                        │
│                  │  (Clean, Chunk) │                        │
│                  └────────┬────────┘                        │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │  Embedding      │                        │
│                  │  Generator      │                        │
│                  └────────┬────────┘                        │
│                           ▼                                  │
│                  ┌─────────────────┐                        │
│                  │    Qdrant       │                        │
│                  │  Vector Store   │                        │
│                  └─────────────────┘                        │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Vector Count | ~1,000 | 50,000+ |
| Search Relevance Score | 0.49-0.56 | 0.75+ |
| Content Coverage | Basic nav text | Comprehensive guides |
| Answer Accuracy | Poor | High (with citations) |

---

## Dependencies to Add

```toml
# pyproject.toml additions
[project.dependencies]
playwright = "^1.40.0"
pymupdf = "^1.23.0"  # For PDF parsing
feedparser = "^6.0.0"  # For RSS parsing
```

---

## References

- ATO RSS Feeds: https://www.ato.gov.au/law/view/rss/index.htm
- ATO Software Developers: https://softwaredevelopers.ato.gov.au/
- ATO API Portal: https://apiportal.ato.gov.au/
- AustLII Tax Database: https://www.austlii.edu.au/au/other/rulings/ato/
- Federal Register of Legislation: https://www.legislation.gov.au/
