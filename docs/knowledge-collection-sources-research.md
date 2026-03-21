# Knowledge Collection Sources Research

Compiled: 2026-03-06
Collections Researched: 5 (Strategic Advisory, Industry Knowledge, Business Fundamentals, Financial Management, People Operations)

---

## Executive Summary

### Totals Across All 5 Collections

| Metric | Value |
|--------|-------|
| Total unique source URLs identified | ~820+ |
| Total estimated source pages | ~5,500-8,300 |
| Total estimated chunks (1,500 chars, 200 overlap) | ~28,000-45,000 |
| Unique source domains | ~40+ |
| Government/regulatory sources | ~95% |
| Authentication-gated (not scrapable) | <5% (CPA/CA ANZ member content) |

### Priority Breakdown

| Priority | URLs | Est. Chunks | Description |
|----------|------|-------------|-------------|
| P1 (Must Have) | ~480 | ~17,000-26,000 | Core authoritative content essential for advisory |
| P2 (Important) | ~230 | ~7,500-12,000 | Valuable supplementary content |
| P3 (Nice to Have) | ~110 | ~3,500-7,000 | Contextual/reference content |

### Implementation Recommendations

1. **Reuse existing scrapers** (`ato_web`, `ato_api` PDF, `ato_rss`) for ~60% of P1 sources -- they are all on `ato.gov.au`
2. **Build 4-5 new scrapers** extending `BaseScraper`: `fairwork_web`, `gov_au_web` (business.gov.au + ASIC + OAIC + IP Australia), `state_revenue_web`, `data_xlsx` (data.gov.au + ABS + RBA tabular data), `homeaffairs_web`
3. **Phase 1 alone** (P1 sources, ~480 URLs, ~17,000-26,000 chunks) would provide comprehensive coverage for all 5 collections using mostly existing infrastructure
4. **Overlap sources** (ATO benchmarks, FBT, business structures, Fair Work) appear across 2-4 collections -- ingest once with multi-collection metadata tags

---

## Collection 1: Strategic Advisory

### Purpose and Value

Provides AI-powered guidance on complex tax planning strategies, business succession, CGT concessions, trust taxation, superannuation strategies, and R&D incentives. This is the highest-value collection for differentiating Clairo's advisory capabilities -- it transforms accountants from reactive compliance workers to proactive strategic advisors.

### Source Summary Table

| Source Name | URL | Content Type | Priority | Est. Pages | Scrape Difficulty |
|-------------|-----|-------------|----------|------------|-------------------|
| ATO Tax Governance Guide (15 pages) | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/privately-owned-and-wealthy-groups/tax-governance/tax-governance-guide-for-privately-owned-groups | Guide series | P1 | 85 | Easy (HTML) |
| ATO Business Closing/Selling Guides | https://www.ato.gov.au/businesses-and-organisations/starting-registering-or-closing-a-business/changing-selling-or-closing-your-business/changing-pausing-closing-selling-or-winding-up-a-business | Guide | P2 | 13 | Easy (HTML) |
| business.gov.au Succession Planning | https://business.gov.au/planning/business-plans/develop-your-succession-plan | Guide | P2 | 5 | Easy (HTML) |
| SB CGT Concessions (Div 152) - 8 pages | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/small-business-cgt-concessions | Guide series | P1 | 55 | Easy (HTML) |
| CGT General Guides & Rollovers | https://www.ato.gov.au/forms-and-instructions/guide-to-capital-gains-tax-2025 | Guide | P1 | 130 | Medium (large) |
| Key ATO Rulings on CGT (LCR 2016/2, 2016/3) | https://www.ato.gov.au/law/view/document?DocID=COG/LCG20163/NAT/ATO/00001 | Rulings | P1 | 90 | Hard (PDF/Legal DB) |
| Division 7A (19 pages) | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/private-company-benefits-division-7a-dividends | Guide series | P1 | 120 | Easy (HTML) |
| Trust Taxation (10 pages) | https://www.ato.gov.au/businesses-and-organisations/trusts | Guide series | P1 | 80 | Easy (HTML) |
| Section 100A (TR 2022/4, PCG 2022/2) | https://www.ato.gov.au/businesses-and-organisations/trusts/trust-income-losses-and-capital-gains/trust-taxation-reimbursement-agreement | Rulings | P1 | 100 | Medium (Legal DB) |
| PSI Rules | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income | Guide | P2 | 10 | Easy (HTML) |
| Part IVA Guide | https://www.ato.gov.au/assets/0/104/997/1030/6f068803-a0d3-406a-b7bc-4d44615af99f.pdf | PDF Guide | P1 | 30 | Hard (PDF) |
| SMSF Guidance (12 pages) | https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/self-managed-super-funds-smsf | Guide series | P1 | 60 | Easy (HTML) |
| Super Contribution Strategies (7 pages) | https://www.ato.gov.au/individuals-and-families/super-for-individuals-and-families/super/growing-and-keeping-track-of-your-super/caps-limits-and-tax-on-super-contributions | Guide series | P1 | 35 | Easy (HTML) |
| R&D Tax Incentive ATO (8 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/research-and-development-tax-incentive-and-concessions/research-and-development-tax-incentive | Guide series | P1 | 40 | Easy (HTML) |
| R&D Tax Incentive business.gov.au (6 pages) | https://business.gov.au/grants-and-programs/research-and-development-tax-incentive | Guide | P1 | 35 | Easy (HTML) |
| SB Concessions & Depreciation (8 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/incentives-and-concessions/concessions | Guide series | P1-P2 | 45 | Easy (HTML) |
| FBT & Salary Sacrifice (8 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax | Guide series | P1 | 150 | Easy-Medium |
| ESS & Innovation (5 pages) | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes | Guide | P2 | 30 | Easy (HTML) |
| Key Person Insurance Rulings | https://www.ato.gov.au/law/view/document?docid=ITR/IT155/NAT/ATO/00001 | Rulings | P2 | 30 | Medium (Legal DB) |
| International Tax for SMEs (5 pages) | https://www.ato.gov.au/businesses-and-organisations/international-tax-for-business/private-wealth-international-program/new-international-tax-measures-affecting-private-groups | Guide | P2 | 40 | Easy (HTML) |
| ATO SB Benchmarks (5 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/small-business-benchmarks | Guide | P1 | 25 | Easy (HTML) |
| State Revenue Offices (14 pages) | Various (revenue.nsw.gov.au, sro.vic.gov.au, qro.qld.gov.au, etc.) | Guide | P2-P3 | 85 | Easy (HTML) |
| ASIC Business Restructuring | https://www.asic.gov.au/regulatory-resources/insolvency/insolvency-for-directors/small-business-restructuring-and-the-restructuring-plan/ | Guide/Report | P2-P3 | 40 | Easy-Hard |
| ATO Areas of Focus 2025-26 | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/privately-owned-and-wealthy-groups/what-attracts-our-attention/areas-of-focus | Guide | P1 | 25 | Easy (HTML) |

### Recommended Scraper Strategy

- **`ato_web` (existing)**: Covers ~130 URLs of static ATO HTML content (~80% of sources)
- **`ato_api` PDF (existing)**: Handles ~8 PDF sources (Advanced CGT guide, Part IVA guide, ASIC reports)
- **ATO Legal DB enhancement**: ~15 URLs need Legal DB parsing (rulings, determinations) -- extend `ato_web` with Legal DB-specific selectors
- **`state_revenue_web` (new)**: For NSW/VIC/QLD/SA/WA revenue office content (~14 URLs)

### Estimated Volume

| Metric | Value |
|--------|-------|
| Total URLs | ~158 |
| Total pages | ~1,290 |
| Total chunks | ~6,300-9,400 |
| P1 chunks | ~4,500-6,800 |

---

## Collection 2: Industry Knowledge

### Purpose and Value

Provides industry-specific knowledge enabling Clairo to contextualise advice per client's industry: ATO benchmarks, industry-specific deduction rules, GST classification by sector, compliance risk areas by industry, and Fair Work award requirements. Critical for the "compare your client against their industry" advisory use case.

### Source Summary Table

| Source Name | URL | Content Type | Priority | Est. Pages | Scrape Difficulty |
|-------------|-----|-------------|----------|------------|-------------------|
| ATO Benchmarks A-Z (100 industries) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/small-business-benchmarks/benchmarks-a-z | Benchmark data | P1 | 200-500 | Easy (HTML) |
| SB Benchmarks XLSX (data.gov.au) | https://data.gov.au/data/dataset/small-business-benchmarks | XLSX datasets | P1 | 8 files | Easy (direct download) |
| ATO Taxation Statistics - Industry | https://www.ato.gov.au/about-ato/research-and-statistics/in-detail/taxation-statistics/taxation-statistics-2022-23/statistics/industry-benchmarks | Statistical tables | P2 | 50 | Medium (HTML+XLSX) |
| ATO Occupation/Industry Guides (41 guides) | https://www.ato.gov.au/individuals-and-families/income-deductions-offsets-and-records/guides-for-occupations-and-industries/occupation-and-industry-specific-guides | Deduction guides | P1 | 200-400 | Easy (HTML) |
| ATO Tax Time Toolkits (40 PDFs) | https://www.ato.gov.au/tax-and-super-professionals/for-tax-professionals/prepare-and-lodge/tax-time/tax-time-toolkits | PDF summaries | P2 | 100-160 | Hard (PDF) |
| ATO SB Compliance Focus Areas | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/our-focus-areas-for-small-business | Compliance guidance | P1 | 15-20 | Easy (HTML) |
| ATO Areas of Focus (Private Groups) | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/privately-owned-and-wealthy-groups/what-attracts-our-attention/areas-of-focus | Compliance guidance | P1 | 10-15 | Easy (HTML) |
| ATO Shadow Economy | https://www.ato.gov.au/about-ato/tax-avoidance/shadow-economy | Enforcement data | P1 | 10-15 | Easy (HTML) |
| ATO Tax Gap Estimates | https://www.ato.gov.au/about-ato/research-and-statistics/in-detail/tax-gap/australian-tax-gaps-overview | Statistical data | P2 | 20-30 | Easy (HTML) |
| ATO GST Industry Guidance (property, food, health, financial, transport, agriculture, gambling) | https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst/in-detail/your-industry/ | Industry GST rules | P1 | 60-80 | Easy (HTML) |
| ATO Primary Producers (9 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/primary-producers | Tax guidance | P1 | 30-40 | Easy (HTML) |
| ATO Property & Construction (9 pages) | https://www.ato.gov.au/businesses-and-organisations/assets-and-property/property/property-development-building-and-renovating | Tax guidance | P1 | 40-50 | Easy (HTML) |
| ATO TPAR (4 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/reports-and-returns/taxable-payments-annual-report | Reporting guide | P1 | 15-20 | Easy (HTML) |
| ATO Employee vs Contractor - Industry Examples | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/employee-or-independent-contractor/difference-between-employees-and-independent-contractors/industry-examples | Industry examples | P1 | 15-20 | Easy (HTML) |
| ATO PSI Rules | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/personal-services-income | Tax guidance | P1 | 10-15 | Easy (HTML) |
| ATO Service Entity Arrangements (3 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business/service-entities/service-entity-arrangements | Tax guidance | P1 | 15-20 | Easy (HTML) |
| ATO NFP Organisations (6 pages) | https://www.ato.gov.au/businesses-and-organisations/not-for-profit-organisations | Tax guidance | P1 | 30-40 | Easy (HTML) |
| ATO Sharing Economy (3 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/sharing-economy-and-tax | Tax guidance | P2 | 10-15 | Easy (HTML) |
| ATO Effective Life by Industry (TR 2022/1) | https://www.ato.gov.au/law/view/print?DocID=TXR/TR20221/NAT/ATO/00003 | Depreciation tables | P2 | 200-500 | Hard (Legal DB) |
| ATO R&D Industry Overview | https://www.ato.gov.au/.../r-d-industry-overview | Statistical data | P3 | 5-10 | Easy (HTML) |
| Fair Work Modern Awards (122 awards, 12-15 key) | https://www.fairwork.gov.au/employment-conditions/awards/list-of-awards | Award summaries | P1 | 600-1,200 | Medium (some JS) |
| Fair Work Pay Guides (PDFs) | https://www.fairwork.gov.au/pay-and-wages/minimum-wages/pay-guides | PDF pay tables | P2 | 122 PDFs | Hard (PDF) |
| Fair Work Industry Guidance | https://www.fairwork.gov.au/find-help-for/ | Industry guides | P2 | 20-30 | Easy-Medium |
| business.gov.au Industry Info (19 sectors) | https://business.gov.au/planning/industry-information | Industry overviews | P2 | 100-190 | Easy (HTML) |
| ABS Australian Industry Statistics | https://www.abs.gov.au/statistics/industry/industry-overview/australian-industry/latest-release | Statistical data | P3 | 20-30 | Medium (HTML+XLSX) |
| ABS Counts of Australian Businesses | https://www.abs.gov.au/statistics/economy/business-indicators/counts-australian-businesses-including-entries-and-exits/latest-release | Statistical data | P3 | 10-20 | Medium (HTML+XLSX) |
| Safe Work Australia Codes of Practice | https://www.safeworkaustralia.gov.au/law-and-regulation/codes-practice | WHS codes | P3 | 100-250 | Hard (PDF) |
| ACNC Governance Hub | https://www.acnc.gov.au/for-charities/manage-your-charity/governance-hub | NFP governance | P2 | 20-30 | Easy (HTML) |
| Jobs & Skills Australia Industry Profiles | https://www.jobsandskills.gov.au/data/occupation-and-industry-profiles/industries | Employment data | P3 | 60-100 | Medium (some JS) |

### Recommended Scraper Strategy

- **`ato_web` (existing)**: Covers ~70% of P1 sources (benchmarks HTML, occupation guides, compliance areas, GST industry, primary producers, property, TPAR, PSI, NFP)
- **`ato_api` PDF (existing)**: Tax time toolkit PDFs
- **`data_gov_xlsx` (new)**: data.gov.au benchmark XLSX datasets -- simple HTTP download + openpyxl parse
- **`fairwork_web` (new)**: Fair Work award summaries, pay guides, industry guides
- **`gov_au_web` (new)**: business.gov.au industry info, ACNC

### Estimated Volume

| Metric | Value |
|--------|-------|
| Total source groups | ~29 |
| Total pages | ~1,760-3,280 |
| Total chunks | ~6,200-11,500 |
| P1 chunks | ~4,000-6,500 |

---

## Collection 3: Business Fundamentals

### Purpose and Value

Foundational business knowledge covering structures, registrations, GST, BAS, PAYG, superannuation, record keeping, director duties, consumer law, privacy, IP, AML/CTF, and WHS. This is the broadest collection, serving as the knowledge base for answering everyday accountant and business owner questions about running a compliant business in Australia.

### Source Summary Table

| Source Name | URL | Content Type | Priority | Est. Pages | Scrape Difficulty |
|-------------|-----|-------------|----------|------------|-------------------|
| business.gov.au Starting/Structures (7 pages) | https://business.gov.au/guide/starting | Step-by-step guide | P1 | 35-50 | Easy (HTML) |
| business.gov.au Registrations (6 pages) | https://business.gov.au/registrations | Guide series | P1 | 17-28 | Easy (HTML) |
| business.gov.au Planning (6 pages) | https://business.gov.au/planning | Guide series | P1 | 26-41 | Easy (HTML) |
| business.gov.au Finance (5 pages) | https://business.gov.au/finance/set-up-your-finances/setting-up-your-finances-checklist | Guide/Checklist | P1 | 14-23 | Easy (HTML) |
| business.gov.au People/Hiring (12 pages) | https://business.gov.au/people/employees | Guide series | P1 | 36-55 | Easy (HTML) |
| business.gov.au Legal/Fair Trading (6 pages) | https://business.gov.au/legal/legal-essentials-for-business | Guide series | P1 | 19-31 | Easy (HTML) |
| business.gov.au Risk/Insurance (11 pages) | https://business.gov.au/risk-management | Guide series | P1 | 38-60 | Easy (HTML) |
| business.gov.au WHS (4 pages) | https://business.gov.au/risk-management/health-and-safety | Guide | P1 | 13-21 | Easy (HTML) |
| business.gov.au Disputes (6 pages) | https://business.gov.au/people/disputes | Guide series | P2 | 16-26 | Easy (HTML) |
| business.gov.au Exiting/Closing (5 pages) | https://business.gov.au/exiting | Guide series | P1 | 17-27 | Easy (HTML) |
| ATO Starting a Business (5 pages) | https://www.ato.gov.au/businesses-and-organisations/starting-registering-or-closing-a-business/starting-your-own-business | Guide series | P1 | 17-28 | Easy (HTML) |
| ATO GST (7 pages) | https://www.ato.gov.au/businesses-and-organisations/gst-excise-and-indirect-taxes/gst | Guide series | P1 | 29-49 | Easy (HTML) |
| ATO BAS (7 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas | Guide series | P1 | 23-38 | Easy (HTML) |
| ATO PAYG (3 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/payg-instalments | Guide series | P1 | 11-18 | Easy (HTML) |
| ATO Super for Employers (5 pages) | https://www.ato.gov.au/businesses-and-organisations/super-for-employers | Guide series | P1 | 19-33 | Easy (HTML) |
| ATO STP (2 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/single-touch-payroll | Guide | P1 | 10-18 | Easy (HTML) |
| ATO FBT (4 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax | Guide series | P1 | 16-26 | Easy (HTML) |
| ATO Record Keeping (8 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/record-keeping-for-business | Guide series | P1 | 30-48 | Easy (HTML) |
| ATO Income Tax/Deductions (9 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/income-and-deductions-for-business | Guide series | P1 | 33-56 | Easy (HTML) |
| ATO TPAR (4 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/reports-and-returns/taxable-payments-annual-report | Guide series | P2 | 12-20 | Easy (HTML) |
| ATO Closing a Business (3 pages) | https://www.ato.gov.au/businesses-and-organisations/starting-registering-or-closing-a-business/changing-selling-or-closing-your-business | Guide series | P1 | 11-18 | Easy (HTML) |
| ASIC Company Registration (6 pages) | https://www.asic.gov.au/for-business-and-companies/companies/register-a-company/ | Guide series | P1 | 22-36 | Easy (HTML) |
| ASIC Director Duties (7 pages) | https://www.asic.gov.au/for-business-and-companies/companies/company-officeholder-rules-and-changes/obligations-of-company-officeholders/ | Guide series | P1 | 25-42 | Easy (HTML) |
| ASIC Annual Compliance (2 pages) | https://asic.gov.au/for-business/running-a-company/annual-statements/ | Guide | P1 | 6-10 | Easy (HTML) |
| ASIC Business Names (5 pages) | https://asic.gov.au/for-business/registering-a-business-name/ | Guide series | P1 | 14-21 | Easy (HTML) |
| ASIC Insolvency/Wind-Up (12 pages) | https://www.asic.gov.au/for-business-and-companies/companies/company-deregistration-and-winding-up/ | Guide series | P1 | 43-68 | Easy (HTML) |
| Fair Work NES (6 pages) | https://www.fairwork.gov.au/employment-conditions/national-employment-standards | Guide/Fact sheet | P1 | 18-29 | Easy (HTML) |
| Fair Work Leave (4 pages) | https://www.fairwork.gov.au/leave | Guide series | P1 | 19-30 | Easy (HTML) |
| Fair Work Hiring/Employment (7 pages) | https://www.fairwork.gov.au/starting-employment/types-of-employees/casual-employees | Guide series | P1 | 25-42 | Easy (HTML) |
| Fair Work Ending Employment (6 pages) | https://www.fairwork.gov.au/ending-employment | Guide series | P1 | 24-37 | Easy (HTML) |
| Fair Work Small Business Showcase (7 pages) | https://smallbusiness.fairwork.gov.au/ | Guide series | P1 | 22-36 | Easy (HTML) |
| Fair Work Templates/Best Practice (3 pages) | https://www.fairwork.gov.au/tools-and-resources/templates | Templates | P2 | 13-21 | Easy (HTML) |
| ACCC Consumer Law (6 pages) | https://www.accc.gov.au/business/selling-products-and-services | Guide/PDF | P1 | 34-51 | Easy-Medium |
| ACCC Small Business (2 pages) | https://www.accc.gov.au/business/small-business | Guide/PDF | P1 | 23-35 | Easy-Medium |
| ACCC Unfair Contract Terms (2 pages) | https://www.accc.gov.au/business/selling-products-and-services/small-business-toolkit/unfair-contract-terms/ | Guide | P1 | 6-10 | Easy (HTML) |
| ACCC Franchising (6 pages) | https://www.accc.gov.au/by-industry/franchising | Guide | P2 | 20-33 | Easy (HTML) |
| OAIC Privacy (10 pages) | https://www.oaic.gov.au/privacy/privacy-guidance-for-organisations-and-government-agencies/organisations/small-business | Guide series | P1-P2 | 45-70 | Easy (HTML) |
| IP Australia (9 pages) | https://www.ipaustralia.gov.au/understanding-ip/types-of-ip | Guide series | P1-P2 | 30-50 | Easy (HTML) |
| Payroll Tax Australia (9 pages) | https://www.payrolltax.gov.au/ | Guide/Reference | P1-P2 | 30-50 | Easy (HTML) |
| State/Territory Business Portals (17 pages) | Various (service.nsw.gov.au, business.vic.gov.au, etc.) | Guide series | P2-P3 | 75-115 | Easy-Medium |
| AUSTRAC AML/CTF (14 pages) | https://www.austrac.gov.au/business/new-to-austrac/your-obligations | Guide series | P1 | 65-100 | Easy (HTML) |
| Safe Work Australia (4 pages) | https://www.safeworkaustralia.gov.au/safety-topic/industry-and-business/small-business | Guide | P2-P3 | 20-32 | Easy (HTML) |

### Recommended Scraper Strategy

- **`ato_web` (existing)**: All ATO content (~57 URLs)
- **`gov_au_web` (new)**: business.gov.au (~68 URLs), ASIC, OAIC, IP Australia, payrolltax.gov.au, AUSTRAC -- all are static HTML government sites with similar structure
- **`fairwork_web` (new)**: Fair Work Ombudsman + Small Business Showcase (~33 URLs)
- **`ato_api` PDF (existing)**: ACCC PDFs, ASIC RG 217, IP Australia quick reference
- **State portal scrapers**: Low priority, standard HTML

### Estimated Volume

| Metric | Value |
|--------|-------|
| Total URLs | ~269 |
| Total pages | ~1,065-1,607 |
| Total chunks | ~3,640-5,540 |
| P1 chunks | ~2,500-3,800 |

---

## Collection 4: Financial Management

### Purpose and Value

Equips the AI to advise on cash flow management, financial benchmarking, budgeting, funding options, debt management, payment terms, business valuation, and financial KPIs. Powers the "financial health check" and "cash flow coaching" advisory workflows that accountants use to move beyond compliance into valued advisory services.

### Source Summary Table

| Source Name | URL | Content Type | Priority | Est. Pages | Scrape Difficulty |
|-------------|-----|-------------|----------|------------|-------------------|
| ATO SB Benchmarks XLSX (data.gov.au) | https://data.gov.au/data/dataset/small-business-benchmarks | XLSX datasets | P1 | 6-8 files | Easy (direct download) |
| ATO SB Benchmarks Website (5 pages) | https://www.ato.gov.au/businesses-and-organisations/income-deductions-and-concessions/small-business-benchmarks | Guide series | P1 | 8-10 | Easy (HTML) |
| ATO Taxation Statistics - Industry | https://www.ato.gov.au/about-ato/research-and-statistics/in-detail/taxation-statistics/taxation-statistics-2022-23/statistics/industry-benchmarks | Statistical tables | P1 | 5 tables | Medium (HTML+XLSX) |
| ATO Cash Flow Coaching Kit (4 pages) | https://www.ato.gov.au/tax-and-super-professionals/for-tax-professionals/support-and-communication/in-detail/cash-flow-coaching-kit | Guide + PDF kit | P1 | 10-15 | Easy (HTML+PDF) |
| ATO Cash Flow & Business Guides (5 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/record-keeping-for-business/setting-up-and-managing-records/manage-your-business-cash-flow | Guide | P1 | 8-10 | Easy (HTML) |
| ATO Payment Plans & Debt (7 pages) | https://www.ato.gov.au/individuals-and-families/paying-the-ato/help-with-paying/payment-plans | Guide series | P1 | 10-12 | Easy (HTML) |
| ATO BAS / Activity Statements (6 pages) | https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas | Guide series | P2 | 10-12 | Easy (HTML) |
| business.gov.au Cash Flow (5 pages) | https://business.gov.au/finance/cash-flow | Guide series | P1 | 6-8 | Easy (HTML) |
| business.gov.au Funding (5 pages) | https://business.gov.au/finance/funding | Guide series | P1 | 6-8 | Easy (HTML) |
| business.gov.au Payments/Invoicing (6 pages) | https://business.gov.au/finance/payments-and-invoicing | Guide series | P2 | 6-8 | Easy (HTML) |
| business.gov.au Financial Setup/Health/EOFY (10 pages) | https://business.gov.au/finance/set-up-your-finances | Guide/Checklist | P2 | 8-10 | Easy (HTML) |
| business.gov.au Tax Guides (8 pages) | https://business.gov.au/finance/tax | Guide series | P2 | 8-10 | Easy (HTML) |
| business.gov.au Pricing Strategy | https://business.gov.au/products-and-services/choose-a-pricing-strategy | Guide | P2 | 1-2 | Easy (HTML) |
| business.gov.au Risk/Insurance (5 pages) | https://business.gov.au/risk-management | Guide series | P2 | 5-6 | Easy (HTML) |
| business.gov.au Planning (3 pages) | https://business.gov.au/planning/business-plans | Guide series | P2 | 4-5 | Easy (HTML) |
| ASIC MoneySmart (6 pages) | https://moneysmart.gov.au/work-and-tax/self-employment | Guide | P2 | 8-10 | Easy (HTML) |
| ASIC Financial Reporting (6 pages) | https://www.asic.gov.au/regulatory-resources/financial-reporting-and-audit/directors-and-financial-reporting/ | Regulatory guidance | P2 | 8-10 | Easy (HTML) |
| ABS Australian Industry | https://www.abs.gov.au/statistics/industry/industry-overview/australian-industry/latest-release | Statistical release | P1 | 5+ files | Medium (HTML+XLSX) |
| ABS Business Indicators (quarterly) | https://www.abs.gov.au/statistics/economy/business-indicators/business-indicators-australia/dec-2025 | Statistical release | P2 | 3-4 | Medium (HTML+XLSX) |
| ABS Counts of Australian Businesses | https://www.abs.gov.au/statistics/economy/business-indicators/counts-australian-businesses-including-entries-and-exits/latest-release | Statistical release | P2 | 3-4 | Medium (HTML+XLSX) |
| ABS CPI | https://www.abs.gov.au/statistics/economy/price-indexes-and-inflation/consumer-price-index-australia/latest-release | Statistical release | P3 | 2-3 | Medium |
| ABS Industry Productivity | https://www.abs.gov.au/statistics/industry/industry-overview/estimates-industry-multifactor-productivity/latest-release | Statistical release | P3 | 2-3 | Medium |
| RBA Cash Rate & Interest Rates (6 pages) | https://www.rba.gov.au/statistics/cash-rate/ | Data (CSV/XLSX) | P2 | 5-6 | Easy-Medium |
| RBA Chart Pack & Outlook (5 pages) | https://www.rba.gov.au/chart-pack/ | PDF + HTML | P2 | 40-50 | Medium (PDF) |
| PPSR Education Hub (15 pages) | https://www.ppsr.gov.au/about-us/about-ppsr | Guide/Case studies | P2 | 20-25 | Easy (HTML) |
| CA ANZ Benchmarks (public) (6 pages) | https://www.charteredaccountantsanz.com/news-and-analysis/insights/research-and-insights/ca-anz-launches-fifth-annual-benchmark-reports | Reports/Tools | P2 | 10-15 | Hard (some gated) |
| CPA Australia SB Resources (public) (9 pages) | https://www.cpaaustralia.com.au/tools-and-resources/business-management/small-business-resources | Guide/Tools | P2 | 10-12 | Hard (some gated) |
| State Govt Grants (all 6 states) | Various (service.nsw.gov.au, business.vic.gov.au, etc.) | Grant directories | P3 | 30-40 | Easy-Medium |
| ASBFEO Resources (13 pages) | https://www.asbfeo.gov.au/resources-tools-centre | Guide/Data/PDF | P2 | 15-20 | Easy-Medium |
| ACCC Pricing (4 pages) | https://www.accc.gov.au/business/pricing | Guide | P3 | 5-6 | Easy (HTML) |

### Recommended Scraper Strategy

- **`ato_web` (existing)**: ATO benchmarks, cash flow, payment plans, BAS content
- **`gov_au_web` (new)**: business.gov.au finance section, PPSR, ASBFEO
- **`data_xlsx` (new)**: data.gov.au XLSX datasets, ABS XLSX, RBA CSV/XLSX -- download + parse tabular data
- **`asic_web` (new or extend `gov_au_web`)**: MoneySmart, ASIC financial reporting
- **`rba_data` (new)**: RBA statistical tables (CSV/XLSX) and chart pack (PDF)
- **`prof_body_web` (new)**: CA ANZ and CPA Australia public pages only

### Estimated Volume

| Metric | Value |
|--------|-------|
| Total URLs | ~120+ |
| Total pages | ~300-380 |
| Total chunks | ~2,500-3,500 |
| P1 chunks | ~700-900 |

---

## Collection 5: People Operations

### Purpose and Value

Covers the full spectrum of employer obligations: PAYG withholding, STP Phase 2, superannuation (including Payday Super from July 2026), FBT, employee vs contractor determination, salary sacrifice, termination payments, Fair Work compliance (NES, awards, leave, dismissal), WHS, payroll tax (all 7 states/territories), workers compensation, immigration/visa worker rules, and paid parental leave. Essential for accountants managing payroll and HR compliance for their clients.

### Source Summary Table

| Source Name | URL | Content Type | Priority | Est. Pages | Scrape Difficulty |
|-------------|-----|-------------|----------|------------|-------------------|
| ATO PAYG Withholding (12 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/payg-withholding | Guide series | P1 | 51 | Easy (HTML) |
| ATO STP Phase 2 (12 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/single-touch-payroll | Guide series | P1 | 66 | Easy (HTML) |
| ATO Super/Payday Super (15 pages) | https://www.ato.gov.au/businesses-and-organisations/super-for-employers | Guide series | P1 | 68 | Easy (HTML) |
| ATO FBT (14 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax | Guide series + PDF | P1 | 80 (HTML) + 300 (PDF) | Easy-Hard |
| ATO ESS (5 pages) | https://www.ato.gov.au/businesses-and-organisations/corporate-tax-measures-and-assurance/employee-share-schemes | Guide | P2 | 24 | Easy (HTML) |
| ATO Employee vs Contractor (5 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/employee-or-independent-contractor | Guide series | P1 | 20 | Easy (HTML) |
| ATO Salary Sacrifice (4 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/fringe-benefits-tax/salary-sacrificing | Guide series | P1 | 18 | Easy (HTML) |
| ATO Termination Payments (6 pages) | https://www.ato.gov.au/businesses-and-organisations/hiring-and-paying-your-workers/engaging-a-worker/when-a-worker-leaves-your-business/taxation-of-termination-payments | Guide series | P1 | 24 | Easy (HTML) |
| Fair Work NES & Conditions (4 pages) | https://www.fairwork.gov.au/employment-conditions/national-employment-standards | Guide/Fact sheet | P1 | 16 | Easy (HTML) |
| Fair Work Awards (5 pages) | https://www.fairwork.gov.au/employment-conditions/awards | Guide/Reference | P1 | 36 | Easy (HTML) |
| Fair Work Pay & Wages (7 pages) | https://www.fairwork.gov.au/pay-and-wages | Guide series | P1 | 24 | Easy (HTML) |
| Fair Work Leave (8 pages) | https://www.fairwork.gov.au/leave | Guide/Fact sheet | P1 | 29 | Easy (HTML) |
| Fair Work Ending Employment (7 pages) | https://www.fairwork.gov.au/ending-employment | Guide/Fact sheet | P1 | 30 | Easy (HTML) |
| Fair Work Fact Sheets & Best Practice (10 pages) | https://www.fairwork.gov.au/tools-and-resources/fact-sheets | Guide series | P1-P2 | 42 | Easy (HTML) |
| Fair Work Small Business (4 pages) | https://smallbusiness.fairwork.gov.au/ | Guide | P2 | 13 | Easy (HTML) |
| Fair Work Commission (3 pages) | https://www.fwc.gov.au/what-small-business-fair-dismissal-code | Guide | P1 | 14 | Easy (HTML) |
| Safe Work Australia WHS (8 pages) | https://www.safeworkaustralia.gov.au/law-and-regulation/codes-practice | Guide + PDF codes | P1-P2 | 30 (HTML) + 135 (PDF) | Medium |
| Services Australia PPL (7 pages) | https://www.servicesaustralia.gov.au/paid-parental-leave-scheme-for-employers | Guide | P1-P2 | 30 | Easy (HTML) |
| State Revenue - Payroll Tax NSW (5 pages) | https://www.revenue.nsw.gov.au/taxes-duties-levies-royalties/payroll-tax | Guide/Reference | P1 | 18 | Easy (HTML) |
| State Revenue - Payroll Tax VIC (5 pages) | https://www.sro.vic.gov.au/businesses-and-organisations/payroll-tax | Guide/Reference | P1 | 19 | Easy (HTML) |
| State Revenue - Payroll Tax QLD (4 pages) | https://qro.qld.gov.au/payroll-tax/ | Guide/Reference | P1 | 16 | Easy (HTML) |
| State Revenue - Payroll Tax SA (4 pages) | https://www.revenuesa.sa.gov.au/payrolltax | Guide + PDF | P1 | 43 | Easy-Hard |
| State Revenue - Payroll Tax WA (4 pages) | https://www.wa.gov.au/government/multi-step-guides/payroll-tax-employer-guide | Guide | P1 | 34 | Easy (HTML) |
| State Revenue - Payroll Tax TAS (2 pages) | https://www.sro.tas.gov.au/payroll-tax | Guide + PDF | P1 | 24 | Easy-Hard |
| State Revenue - Payroll Tax ACT (4 pages) | https://www.revenue.act.gov.au/payroll-tax | Guide | P1 | 15 | Easy (HTML) |
| State Revenue - Payroll Tax NT (3 pages) | https://treasury.nt.gov.au/dtf/territory-revenue-office/payroll-tax | Guide + PDF | P1 | 24 | Easy-Hard |
| Workers Comp NSW (SIRA) (3 pages) | https://www.sira.nsw.gov.au/workers-compensation | Guide | P1 | 17 | Easy (HTML) |
| Workers Comp VIC (WorkSafe) (3 pages) | https://www.worksafe.vic.gov.au/your-workcover-insurance-responsibilities-employer | Guide + PDF | P1 | 25 | Easy-Medium |
| Workers Comp QLD (4 pages) | https://www.worksafe.qld.gov.au/claims-and-insurance/workcover-insurance | Guide + PDF | P1-P2 | 16 | Easy-Hard |
| Workers Comp SA (3 pages) | https://www.rtwsa.com/claims/employer-and-worker-obligations | Guide + PDF | P1-P2 | 24 | Easy-Hard |
| Workers Comp WA (3 pages) | https://www.workcover.wa.gov.au/resources/forms-publications/employer-publications/employer-guides/ | Guide + PDF | P1 | 38 | Easy-Hard |
| Workers Comp TAS (4 pages) | https://www.worksafe.tas.gov.au/topics/compensation/workers-compensation | Guide + PDF | P1-P2 | 52 | Easy-Hard |
| Comcare (3 pages) | https://www.comcare.gov.au/claims/employer-information/claims-information-for-employers | Guide | P2-P3 | 14 | Easy (HTML) |
| Immigration/Home Affairs (13 pages) | https://immi.homeaffairs.gov.au/visas/employing-and-sponsoring-someone/explore-options-for-employers | Guide series | P1-P2 | 69 | Easy (HTML) |

### Recommended Scraper Strategy

- **`ato_web` (existing)**: All ATO content (~73 URLs for PAYG, STP, super, FBT, ESS, contractor, salary sacrifice, terminations)
- **`ato_api` PDF (existing)**: FBT employers guide PDF (~300 pages)
- **`fairwork_web` (new)**: Fair Work Ombudsman + Small Business Showcase + fact sheets (~44 URLs)
- **`fwc_web` (new)**: Fair Work Commission (3 URLs, simple HTML)
- **`state_revenue_web` (new)**: 7 state revenue office sites for payroll tax (~32 URLs) -- configurable scraper with per-domain selectors
- **`workcover_web` (new)**: 7 state workers compensation sites (~23 URLs) -- HTML + PDF
- **`services_aus_web` (new)**: Services Australia PPL pages (~7 URLs)
- **`homeaffairs_web` (new)**: Home Affairs visa/employer pages (~13 URLs)
- **`safework_web` (new)**: Safe Work Australia HTML pages + PDF codes of practice (~8 URLs)

### Estimated Volume

| Metric | Value |
|--------|-------|
| Total URLs | ~203 |
| Total pages (HTML) | ~898 |
| Total pages (PDF) | ~640 |
| Total chunks | ~7,685 |
| P1 chunks | ~4,500 |

---

## Cross-Cutting Analysis

### Overlap Between Collections

Several sources serve multiple collections. These should be ingested once with metadata tags marking all applicable collections:

| Source | Collections | Notes |
|--------|-------------|-------|
| ATO Small Business Benchmarks | Strategic Advisory, Industry Knowledge, Financial Management | Core benchmarking data used for all advisory contexts |
| ATO FBT & Salary Sacrifice | Strategic Advisory, People Operations, Business Fundamentals | Strategic (tax planning), operational (employer compliance), fundamental (basics) |
| ATO Business Structures | Strategic Advisory, Business Fundamentals | Strategic (restructuring), fundamental (setup) |
| Fair Work NES/Awards/Leave | People Operations, Business Fundamentals, Industry Knowledge | Operational (compliance), fundamental (basics), industry (award-specific) |
| ATO Employee vs Contractor | People Operations, Industry Knowledge, Business Fundamentals | Employer compliance + industry-specific examples + foundational knowledge |
| ATO GST Industry Guidance | Industry Knowledge, Business Fundamentals | Industry-specific rules + general GST fundamentals |
| ATO CGT Concessions (Div 152) | Strategic Advisory, Business Fundamentals | Strategic planning + basic understanding |
| ATO Succession/Exit Guides | Strategic Advisory, Business Fundamentals | Strategic planning + general exit procedures |
| business.gov.au Risk/Insurance | Business Fundamentals, Financial Management | General business knowledge + financial risk management |
| ATO Payment Plans & Debt | Financial Management, Business Fundamentals | Financial advisory + compliance basics |
| State Revenue Payroll Tax | People Operations, Business Fundamentals | Employer compliance + foundational obligation |
| ATO R&D Tax Incentive | Strategic Advisory, Industry Knowledge | Strategic planning + industry-specific benefits |
| AUSTRAC AML/CTF | Business Fundamentals (primarily) | Especially relevant for accountants (Tranche 2) |
| ATO Areas of Focus | Strategic Advisory, Industry Knowledge | Compliance risk + industry targeting |

**Deduplication strategy**: Ingest each URL once. Apply multiple `collection` tags in Pinecone metadata (e.g., `["strategic_advisory", "industry_knowledge"]`). Query agents filter by their collection namespace but can also cross-reference.

### Scraping Infrastructure Needs

#### Existing Scrapers (Reusable)

| Scraper | Sources Covered | Est. URLs |
|---------|----------------|-----------|
| `ato_web` | ato.gov.au HTML pages across all 5 collections | ~350 |
| `ato_api` (PDF) | ATO PDFs (guides, rulings, FBT employer guide) | ~20 |
| `ato_rss` | ATO news/updates | Ongoing |

#### New Scrapers Required

| Scraper | Domain(s) | Type | Est. URLs | Difficulty | Priority |
|---------|-----------|------|-----------|------------|----------|
| `gov_au_web` | business.gov.au, asic.gov.au, oaic.gov.au, ipaustralia.gov.au, payrolltax.gov.au, austrac.gov.au, ppsr.gov.au, asbfeo.gov.au, acnc.gov.au | Static HTML | ~180 | Easy | P1 |
| `fairwork_web` | fairwork.gov.au, smallbusiness.fairwork.gov.au, fwc.gov.au | Static HTML + some PDF | ~80 | Easy-Medium | P1 |
| `state_revenue_web` | revenue.nsw.gov.au, sro.vic.gov.au, qro.qld.gov.au, revenuesa.sa.gov.au, wa.gov.au, sro.tas.gov.au, revenue.act.gov.au, treasury.nt.gov.au | Configurable HTML + PDF | ~45 | Easy-Medium | P1 |
| `data_xlsx` | data.gov.au, abs.gov.au, rba.gov.au | XLSX/CSV download + parse | ~20 | Medium | P1 |
| `workcover_web` | sira.nsw.gov.au, worksafe.vic.gov.au, worksafe.qld.gov.au, rtwsa.com, workcover.wa.gov.au, worksafe.tas.gov.au, comcare.gov.au | HTML + PDF | ~25 | Medium-Hard | P2 |
| `homeaffairs_web` | immi.homeaffairs.gov.au | Static HTML | ~15 | Easy | P2 |
| `services_aus_web` | servicesaustralia.gov.au | Static HTML | ~7 | Easy | P2 |
| `safework_web` | safeworkaustralia.gov.au | HTML + PDF codes | ~10 | Medium | P2 |
| `accc_web` | accc.gov.au, consumer.gov.au | HTML + PDF | ~16 | Easy-Medium | P2 |
| `prof_body_web` | charteredaccountantsanz.com, cpaaustralia.com.au | Public HTML only | ~15 | Hard (gated content) | P3 |
| `abs_web` | abs.gov.au | HTML narrative + XLSX | ~10 | Medium | P2 |

### Implementation Roadmap

#### Phase 1: Foundation (P1 Sources, ~480 URLs, ~17,000-26,000 chunks)

**New scrapers needed**: 4 (`gov_au_web`, `fairwork_web`, `state_revenue_web`, `data_xlsx`)

| Step | Action | Scrapers | Collections Served |
|------|--------|----------|-------------------|
| 1.1 | ATO HTML content (all P1 pages across all collections) | `ato_web` (existing) | All 5 |
| 1.2 | ATO PDF content (CGT guide, Part IVA, FBT employer guide, rulings) | `ato_api` (existing) | Strategic Advisory, People Ops |
| 1.3 | business.gov.au full site crawl (starting, planning, finance, people, legal, risk, exiting) | `gov_au_web` (new) | Business Fundamentals, Financial Management |
| 1.4 | ASIC company/directors/insolvency/business names | `gov_au_web` (new) | Business Fundamentals |
| 1.5 | Fair Work NES, awards, pay/wages, leave, ending employment, fact sheets | `fairwork_web` (new) | People Operations, Business Fundamentals |
| 1.6 | Payroll tax -- all 7 states/territories hub + rates pages | `state_revenue_web` (new) | People Operations |
| 1.7 | data.gov.au SB Benchmarks XLSX + ABS Australian Industry XLSX | `data_xlsx` (new) | Industry Knowledge, Financial Management |
| 1.8 | AUSTRAC accountant guidance and AML/CTF obligations | `gov_au_web` (new) | Business Fundamentals |
| 1.9 | ATO Cash Flow Coaching Kit + payment plans | `ato_web` (existing) | Financial Management |

**Estimated delivery**: 4-6 weeks (scrapers + ingestion pipeline)

#### Phase 2: Expansion (P2 Sources, ~230 URLs, ~7,500-12,000 chunks)

**New scrapers needed**: 5 (`workcover_web`, `homeaffairs_web`, `services_aus_web`, `safework_web`, `accc_web`)

| Step | Action | Scrapers |
|------|--------|----------|
| 2.1 | Workers compensation -- all states | `workcover_web` (new) |
| 2.2 | Immigration/Home Affairs visa employer guidance | `homeaffairs_web` (new) |
| 2.3 | Services Australia PPL employer obligations | `services_aus_web` (new) |
| 2.4 | Safe Work Australia WHS codes + psychosocial hazards | `safework_web` (new) |
| 2.5 | ACCC consumer law, franchising, pricing | `accc_web` (new) |
| 2.6 | ATO Legal DB -- rulings (TR 2022/4, PCG 2022/2, LCRs) | Enhanced `ato_web` |
| 2.7 | OAIC privacy guidance (APPs) | `gov_au_web` (existing) |
| 2.8 | IP Australia trade marks guidance | `gov_au_web` (existing) |
| 2.9 | PPSR education hub | `gov_au_web` (existing) |
| 2.10 | ASBFEO resources, payment times, Small Business Pulse | `gov_au_web` (existing) |
| 2.11 | ASIC MoneySmart financial literacy | `gov_au_web` (existing) |
| 2.12 | Fair Work pay guides PDFs, best practice guides, templates | `fairwork_web` (existing) |
| 2.13 | ATO Tax Time Toolkit PDFs (40 occupation PDFs) | `ato_api` (existing) |
| 2.14 | ATO Effective Life by industry (TR 2022/1) | Enhanced `ato_web` |
| 2.15 | business.gov.au industry information (19 sectors) | `gov_au_web` (existing) |
| 2.16 | RBA interest rates, chart pack, economic outlook | `data_xlsx` / `rba_data` (new or extend) |
| 2.17 | ABS Business Indicators, Business Counts | `abs_web` (new or extend `data_xlsx`) |
| 2.18 | ACNC governance hub | `gov_au_web` (existing) |
| 2.19 | State business portals (NSW, VIC, QLD) | `gov_au_web` (existing) |
| 2.20 | State revenue offices -- stamp duty, land tax for restructuring | `state_revenue_web` (existing) |

**Estimated delivery**: 4-6 weeks after Phase 1

#### Phase 3: Enrichment (P3 Sources, ~110 URLs, ~3,500-7,000 chunks)

| Step | Action |
|------|--------|
| 3.1 | Remaining state business portals (SA, WA, TAS) |
| 3.2 | State government grants directories (all 6 states) |
| 3.3 | CA ANZ and CPA Australia public resources |
| 3.4 | ABS CPI, productivity data |
| 3.5 | Safe Work Australia additional codes of practice |
| 3.6 | Jobs & Skills Australia industry profiles |
| 3.7 | ATO sharing economy, international tax details |
| 3.8 | Remaining ATO Legal DB rulings (Part IVA PS LA, ESS, key person insurance) |

**Estimated delivery**: 2-4 weeks after Phase 2

### New Scraper Types Needed

Total new scrapers to build: **10** (4 in Phase 1, 5 in Phase 2, 1 in Phase 3)

All new scrapers should extend `BaseScraper` from `scrapers/base.py` and inherit:
- Tenacity retries (3x exponential backoff)
- Token-bucket rate limiting (1 req/s default, adjustable per domain)
- Semaphore concurrency control (3 concurrent default)
- Content hashing for deduplication
- Structured metadata output for Pinecone upsert

Key design considerations:
1. **`gov_au_web`** should be a configurable HTML scraper with per-domain CSS selectors for content extraction -- most government sites use `<article>`, `<main>`, or `.content-body` wrappers
2. **`data_xlsx`** needs openpyxl for XLSX parsing, with row-by-row chunking that preserves column headers as context. Each industry-metric-year combination should become a separate chunk with structured metadata.
3. **`state_revenue_web`** should support a domain config map for the 7+ state revenue offices, with per-domain rate limits and content selectors
4. **`fairwork_web`** needs to handle both HTML pages and linked PDF fact sheets/pay guides

---

## Appendix: Full Source Catalog by Priority

### P1 Sources (Must Have) -- ~480 URLs

**Strategic Advisory P1 (~95 URLs)**
- ATO Tax Governance Guide for Privately Owned Groups -- all 15 sections
- Small Business CGT Concessions (Div 152) -- all 8 pages
- Division 7A -- all 19 pages
- Trust taxation + Section 100A -- all pages including TR 2022/4, PCG 2022/2
- SMSF and super contribution strategies -- all pages
- R&D Tax Incentive -- ATO (8 pages) + business.gov.au (6 pages)
- Business structures guide
- CGT comprehensive guide 2025
- ATO areas of focus 2025-26
- FBT overview + exemptions + salary sacrifice
- Small business benchmarks overview
- Part IVA guide (PDF)
- Advanced CGT guide (PDF)
- LCR 2016/3 (small business restructure roll-over)

**Industry Knowledge P1 (~100+ URLs)**
- ATO Benchmarks A-Z (100 industry pages)
- SB Benchmarks XLSX datasets from data.gov.au (8 files)
- ATO Occupation/Industry Guides (41 guides)
- ATO Compliance Focus Areas (SB + private groups)
- ATO Shadow Economy
- ATO GST Industry Guidance (property, food, health, financial, transport, agriculture, gambling)
- ATO Primary Producers (9 pages)
- ATO Property & Construction (9 pages)
- ATO TPAR (4 pages)
- ATO Employee vs Contractor Industry Examples
- ATO PSI Rules
- ATO Service Entity Arrangements
- ATO NFP Organisations (6 pages)
- Fair Work key industry awards (top 12-15 awards)

**Business Fundamentals P1 (~180 URLs)**
- business.gov.au: starting, structures, registrations, planning, finance, people/hiring, legal/fair trading, risk/insurance, WHS, exiting (~58 pages)
- ATO: starting, GST, BAS, PAYG, super, STP, FBT, record keeping, income tax/deductions, closing (~50 pages)
- ASIC: company registration, director duties, annual compliance, business names, insolvency/wind-up (~32 pages)
- Fair Work: NES, leave, hiring, ending employment, Small Business Showcase (~30 pages)
- ACCC: selling, small business, unfair contract terms (~10 pages)
- OAIC: small business privacy, APP overview (~2 pages)
- IP Australia: types of IP, trade marks (~2 pages)
- Payroll Tax Australia: overview, registration, rates (~4 pages)
- AUSTRAC: obligations, accountant guidance, program starter kit (~10 pages)

**Financial Management P1 (~35 URLs)**
- ATO SB Benchmarks XLSX datasets
- ATO Benchmarks website (methodology, types)
- ATO Taxation Statistics industry benchmarks
- ATO Cash Flow Coaching Kit
- ATO Cash flow management guides
- ATO Payment plans and debt management
- business.gov.au cash flow section
- business.gov.au funding section
- ABS Australian Industry data

**People Operations P1 (~120 URLs)**
- ATO: PAYG withholding (12), STP Phase 2 (12), Super/Payday Super (15), FBT HTML (14), Employee vs Contractor (5), Salary Sacrifice (4), Termination Payments (6)
- Fair Work: NES (4), Awards (5), Pay/Wages (7), Leave (8), Ending Employment (7), Fact Sheets (10), FWC (3)
- State Revenue payroll tax: all 7 states/territories (~32)
- Workers Comp: NSW, VIC, QLD top-level (~9)
- Home Affairs: employer responsibilities, VEVO, subclass 482 (~8)

### P2 Sources (Important) -- ~230 URLs

- ATO: ESS, in-detail PAYG, FBT employers guide PDF, BAS guides, Legal DB rulings (TR 2022/4, PCG 2022/2, LCRs), Tax Time Toolkit PDFs, Effective Life tables, ATO tax gap, sharing economy
- Fair Work: best practice guides, templates, Small Business Showcase, pay guides PDFs
- State Revenue: stamp duty/land tax for restructuring (NSW, VIC, QLD)
- Workers Comp: SA, WA, TAS, Commonwealth guides
- Home Affairs: subclass 186, 494, skilled occupation list
- Safe Work Australia: psychosocial hazards code, WHS risk management code
- Services Australia: Paid Parental Leave employer pages, FTB
- business.gov.au: payments/invoicing, financial setup/EOFY, tax guides, pricing, risk/insurance, disputes, industry information (19 sectors)
- ASIC: MoneySmart, financial reporting
- OAIC: full APP guidelines
- IP Australia: trade mark application, design rights
- Payroll Tax Australia: harmonisation, lodging, state specifics
- ABS: Business Indicators, Business Counts
- RBA: interest rates, chart pack, economic outlook
- PPSR: education hub
- ASBFEO: resources, payment times, dispute resolution
- ACNC: governance hub
- CA ANZ and CPA Australia: public resources
- State portals: NSW, VIC, QLD business guides

### P3 Sources (Nice to Have) -- ~110 URLs

- Remaining state revenue offices (SA, WA stamp duty/land tax)
- Part IVA detailed practice statement (PS LA 2005/24)
- Additional ATO Legal Database rulings
- ATO benchmarking methodology
- ABS: CPI, productivity data
- State government grants (all 6 states)
- ACCC: pricing obligations
- Safe Work Australia: additional codes of practice, model WHS laws
- Jobs & Skills Australia: industry profiles
- ATO: R&D industry data, international tax details
- Remaining state portals (SA, WA, TAS)
- Fair Work: consultation guide PDF
- Comcare: about the scheme, regulatory guides
- OAIC: remaining APP chapters
- IP Australia: design right application
