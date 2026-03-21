# Spec 012: Knowledge Base Infrastructure - Research

**Created**: 2025-12-29
**Status**: Research Complete
**Branch**: `012-knowledge-base`

---

## Executive Summary

This document captures research for building Clairo's Knowledge Base Infrastructure - the foundation of our AI moat. The knowledge base must serve both **accountants** and **business owners** with authoritative Australian tax compliance and strategic advisory content.

---

## 1. Platform Pillars Alignment

From `/planning/strategy/platform-pillars.md`, the Knowledge Base serves **Pillar 2 (Compliance Knowledge)** and **Pillar 3 (Strategic Advisory)**:

```
┌─────────────────────────────────────────────────────────────────┐
│   PILLAR 2: COMPLIANCE KNOWLEDGE                                │
├─────────────────────────────────────────────────────────────────┤
│   • ATO guidelines, GST rules, BAS requirements                 │
│   • Tax rulings (TR, TD, GSTR, PCG)                            │
│   • PAYG withholding, super guarantee                          │
│   • Deduction categories by industry                            │
│   • Contractor vs employee guidelines                           │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│   PILLAR 3: STRATEGIC ADVISORY                                  │
├─────────────────────────────────────────────────────────────────┤
│   • Entity structuring (trust, company, partnership)            │
│   • Tax optimization strategies                                 │
│   • Cash flow management                                        │
│   • Industry benchmarks and playbooks                           │
│   • Growth strategies                                           │
└─────────────────────────────────────────────────────────────────┘
```

**The Magic Zone** emerges when we combine:
- Client Data (Pillar 1) + Compliance Knowledge (Pillar 2) + Strategic Advisory (Pillar 3)
- = Personalized, proactive, actionable insights

---

## 2. Authoritative Content Sources

### 2.1 Primary ATO Sources (MUST HAVE)

| Source | Content Type | Access Method | Priority |
|--------|--------------|---------------|----------|
| [ATO RSS Feeds](https://www.ato.gov.au/law/view/rss/index.htm) | Rulings, determinations, updates | RSS feeds | P1 |
| [ATO Website](https://www.ato.gov.au) | GST, PAYG, Super, BAS guides | Web scraping | P1 |
| [ATO Legal Database](https://www.ato.gov.au/law) | Tax rulings, interpretations | Web scraping | P1 |
| [ATO API](https://www.ato.gov.au/api/public/content/) | Structured content | REST API | P1 |

**ATO RSS Feeds Available:**
- Taxation Rulings and Determinations (TR, TD)
- GST Rulings and Determinations (GSTR)
- Superannuation Rulings and Determinations
- Practical Compliance Guidelines (PCG)
- Law Administration Practice Statements (PS LA)

**Recent 2024-2025 Rulings to Ingest:**
- PCG 2024/2 - Electric vehicle home charging rate
- PCG 2025/5 - Personal services businesses and Part IVA
- PS LA 2025/2 - Public country-by-country reporting exemptions
- TA 2025/3 - Barter credits deduction arrangements

### 2.2 Legislation Sources (MUST HAVE)

| Source | Content | Access Method | Priority |
|--------|---------|---------------|----------|
| [AustLII](https://www.austlii.edu.au) | ITAA 1936, ITAA 1997, GST Act 1999 | Web scraping / [legaldata package](https://github.com/dylanhogg/legaldata) | P1 |
| [Federal Register of Legislation](https://www.legislation.gov.au) | Official consolidated Acts | Web scraping | P2 |

**Key Acts to Ingest:**
- Income Tax Assessment Act 1997 (ITAA 1997)
- Income Tax Assessment Act 1936 (ITAA 1936)
- A New Tax System (Goods and Services Tax) Act 1999
- Superannuation Guarantee (Administration) Act 1992
- Fringe Benefits Tax Assessment Act 1986
- Tax Administration Act 1953

### 2.3 Industry Bodies (SHOULD HAVE)

| Source | Content | Access Method | Priority |
|--------|---------|---------------|----------|
| [CA ANZ](https://www.charteredaccountantsanz.com) | ATO rulings summaries, technical guidance | Web scraping | P2 |
| [CPA Australia](https://www.cpaaustralia.com.au) | Technical resources, practice guides | Web scraping | P2 |
| [Tax Practitioners Board](https://www.tpb.gov.au) | Registration requirements, CPE | Web scraping | P2 |
| [AustaxPolicy Blog](https://austaxpolicy.com) | Tax policy analysis | RSS feed | P3 |

### 2.4 Industry-Specific Sources (NICE TO HAVE)

| Industry | Source | Content |
|----------|--------|---------|
| Construction | HIA, MBA | Industry deductions, contractor rules |
| Hospitality | AHA | Tips, cash handling, uniforms |
| Professional Services | Law societies, CPA | Home office, CPE, memberships |
| Retail | NRA | Inventory, POS requirements |
| E-commerce | ATO Digital Economy | GST on digital supplies |

### 2.5 Content Update Strategy

```
┌────────────────────────────────────────────────────────────────┐
│                    DAILY                                        │
├────────────────────────────────────────────────────────────────┤
│  • Monitor ATO RSS feeds for new rulings                       │
│  • Flag changes for review queue                               │
│  • Auto-ingest new determinations                              │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                    WEEKLY                                       │
├────────────────────────────────────────────────────────────────┤
│  • Process review queue                                         │
│  • Update affected knowledge chunks                            │
│  • Re-embed modified content                                   │
│  • Validate retrieval quality                                  │
└────────────────────────────────────────────────────────────────┘
                               │
                               ▼
┌────────────────────────────────────────────────────────────────┐
│                    QUARTERLY                                    │
├────────────────────────────────────────────────────────────────┤
│  • Full content audit against ATO website                      │
│  • Rate/threshold updates (July 1 critical)                    │
│  • Expert review of high-impact content                        │
│  • User feedback integration                                   │
└────────────────────────────────────────────────────────────────┘
```

---

## 3. Vector Database: Qdrant vs pgvector

### 3.1 Current Infrastructure

We have **Qdrant** already in docker-compose.yml:
```yaml
qdrant:
  image: qdrant/qdrant:latest
  container_name: clairo-qdrant
  ports:
    - "${QDRANT_HTTP_PORT:-6333}:6333"
    - "${QDRANT_GRPC_PORT:-6334}:6334"
```

### 3.2 Comparison Matrix

| Criterion | Qdrant | pgvector |
|-----------|--------|----------|
| **Performance at Scale** | Degrades beyond 10M vectors | Better at high scale (50M+) with pgvectorscale |
| **Latency** | Better tail latencies at high recall | Order of magnitude better throughput at 99% recall |
| **Metadata Filtering** | Excellent, first-class citizen | Good, but requires careful indexing |
| **Multi-tenancy** | Built-in collection/namespace isolation | Schema or partition-based isolation |
| **Production Readiness** | Mature, ACID compliant | Very mature (PostgreSQL) |
| **Operational Complexity** | Separate service to manage | Same DB as primary data (simpler) |
| **Resource Efficiency** | Runs on smaller instances, edge-friendly | Requires PostgreSQL tuning |
| **Cost** | Additional infrastructure | No additional cost if using PostgreSQL |
| **Rust Implementation** | Yes | Yes (pgvectorscale) |

### 3.3 Recommendation: **Qdrant**

**Rationale:**

1. **Already in our stack** - Qdrant is configured and running in docker-compose
2. **Multi-tenancy first-class** - Built-in collection/namespace isolation perfect for:
   - Tenant isolation (each accounting practice)
   - Content type separation (compliance vs strategic)
   - Industry-specific collections
3. **Metadata filtering excellence** - Critical for RAG queries like:
   - "GST rules for construction industry"
   - "Deductions updated after July 2024"
   - "Rulings applicable to sole traders"
4. **Separation of concerns** - Knowledge base separate from transactional data
5. **Scale considerations** - We're unlikely to exceed 10M vectors for Australian tax content
6. **Edge deployment potential** - Future mobile/offline capabilities

**Benchmarks context:**
- Our expected scale: 1-5M vectors (entire Australian tax corpus)
- At this scale, Qdrant performs excellently
- Degradation concerns (10M+) don't apply to our use case

### 3.4 pgvector as Future Option

Keep pgvector in mind for:
- Client-specific embeddings (e.g., embedding client documents)
- Unified queries across structured and vector data
- If operational simplicity becomes more important than feature richness

---

## 4. Knowledge Base Namespace Strategy

### 4.1 Collection Architecture

```
QDRANT COLLECTION STRUCTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                     COMPLIANCE COLLECTION                        │
│                     (compliance_knowledge)                       │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces:                                                     │
│  ├── gst                    # GST rules, rates, BAS             │
│  ├── income_tax             # PAYG, deductions, thresholds      │
│  ├── superannuation         # SG rates, caps, deadlines         │
│  ├── payroll                # PAYG withholding, STP             │
│  ├── fbt                    # Fringe benefits tax               │
│  ├── rulings                # TR, TD, GSTR, PCG                 │
│  └── legislation            # ITAA 1936, ITAA 1997, GST Act     │
│                                                                  │
│  Metadata per chunk:                                             │
│  ├── source_url             # Origin URL                        │
│  ├── source_type            # ato_website, ruling, legislation  │
│  ├── effective_date         # When rule became effective        │
│  ├── expiry_date            # When rule expires (if any)        │
│  ├── last_updated           # Last scrape/update date           │
│  ├── entity_types           # [sole_trader, company, trust]     │
│  ├── industries             # [construction, retail, etc]       │
│  ├── ruling_number          # TR 2024/1, GSTR 2024/1, etc       │
│  └── confidence_level       # high, medium, low                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     STRATEGIC COLLECTION                         │
│                     (strategic_advisory)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces:                                                     │
│  ├── entity_structure       # Company vs trust vs sole trader   │
│  ├── tax_optimization       # Legal minimization strategies     │
│  ├── cash_flow              # Cash flow improvement tactics     │
│  ├── growth_strategy        # Scaling, hiring, expansion        │
│  └── industry_playbooks     # Sector-specific strategies        │
│                                                                  │
│  Metadata per chunk:                                             │
│  ├── source                 # Book, expert interview, guide     │
│  ├── expert_reviewed        # Boolean                           │
│  ├── review_date            # When expert reviewed              │
│  ├── reviewer_id            # Who reviewed                      │
│  ├── applicable_revenue     # [<75k, 75k-500k, 500k+]          │
│  ├── entity_types           # [sole_trader, company, trust]     │
│  ├── industries             # [construction, retail, etc]       │
│  └── risk_level             # low, medium, high                 │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     INDUSTRY COLLECTION                          │
│                     (industry_knowledge)                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces (by ANZSIC code):                                    │
│  ├── construction_30-32     # Building, civil, trades           │
│  ├── retail_39-43           # Retail trade                      │
│  ├── hospitality_44-45      # Accommodation, food services      │
│  ├── professional_69-70     # Professional services             │
│  ├── healthcare_84-87       # Healthcare and social assistance  │
│  ├── transport_46-53        # Transport and logistics           │
│  └── manufacturing_11-25    # Manufacturing                     │
│                                                                  │
│  Metadata per chunk:                                             │
│  ├── anzsic_code            # Specific ANZSIC code              │
│  ├── deduction_type         # vehicle, tools, uniform, etc      │
│  ├── ato_guide_reference    # Link to ATO industry guide        │
│  └── benchmark_data         # Industry benchmarks if available  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 Multi-Tenant Considerations

For tenant-specific content (future - Phase D):

```
TENANT-SPECIFIC COLLECTION (Future)
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                     TENANT DOCUMENTS                             │
│                     (tenant_{tenant_id}_docs)                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Per-tenant collection for:                                      │
│  ├── Uploaded documents (receipts, contracts)                   │
│  ├── Client-specific notes                                       │
│  ├── Practice-specific procedures                                │
│  └── Custom knowledge additions                                  │
│                                                                  │
│  Isolation: Complete tenant isolation via separate collections  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 4.3 Query Routing Strategy

```python
# Pseudocode for query routing

def route_query(query: str, context: QueryContext) -> list[str]:
    """Determine which collections/namespaces to search."""

    collections = []

    # Always search compliance for tax questions
    if is_compliance_question(query):
        collections.append(("compliance_knowledge", detect_namespace(query)))

    # Add strategic if asking about optimization/growth
    if is_strategic_question(query):
        collections.append(("strategic_advisory", detect_strategy_type(query)))

    # Add industry if client context available
    if context.client_industry:
        collections.append(("industry_knowledge", context.client_industry))

    return collections
```

---

## 5. Embedding Model Selection

### 5.1 Model Comparison

| Model | Accuracy | Cost (per 1M tokens) | Dimensions | Strengths |
|-------|----------|----------------------|------------|-----------|
| **voyage-3-large** | Best in class | ~$0.12 | 1024 | Highest retrieval relevance |
| **voyage-3.5-lite** | 66.1% | $0.02 | 512 | Best accuracy/cost ratio |
| text-embedding-3-large | Good | ~$0.13 | 3072 | OpenAI ecosystem |
| text-embedding-3-small | Moderate | ~$0.02 | 1536 | Budget OpenAI option |
| Cohere Embed v3 | Lower | ~$0.10 | 1024 | 100+ languages |
| BGE-M3 (open source) | Good | Free (self-hosted) | 1024 | No API costs |

### 5.2 Recommendation: **Voyage AI**

**Primary: voyage-3.5-lite** for production
**Fallback: voyage-3-large** for high-stakes queries

**Rationale:**

1. **Purpose-built for RAG** - Voyage AI is built by Stanford researchers specializing in RAG
2. **Tricky negatives training** - Explicitly trained to distinguish similar but different concepts (critical for tax law where subtle differences matter)
3. **Best accuracy/cost ratio** - voyage-3.5-lite at $0.02/1M tokens with 66.1% accuracy
4. **Tax-specific benefit** - Legal/compliance text benefits from models trained on nuanced distinctions

**Example critical distinction:**
- "GST-free supplies" vs "Input-taxed supplies" - similar wording, completely different tax treatment
- Voyage's training on "tricky negatives" handles this better than general-purpose embeddings

### 5.3 Dimension Strategy

| Use Case | Model | Dimensions | Storage |
|----------|-------|------------|---------|
| Compliance knowledge | voyage-3.5-lite | 512 | ~2KB/chunk |
| Strategic advisory | voyage-3.5-lite | 512 | ~2KB/chunk |
| High-stakes queries | voyage-3-large | 1024 | ~4KB/chunk |

**512 dimensions recommended** for:
- Lower storage costs
- Faster similarity search
- Sufficient for tax/compliance domain

### 5.4 Open Source Alternative

If API costs become a concern, consider:
- **BGE-M3** - Self-hosted, good accuracy, no per-query cost
- Trade-off: Requires GPU infrastructure for embedding generation

---

## 6. Technical Architecture Summary

```
KNOWLEDGE BASE ARCHITECTURE
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                    INGESTION PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Sources                    Processing                           │
│  ───────                    ──────────                           │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │   ATO    │───▶│  Scraper │───▶│  Chunker │───▶│ Embedder │  │
│  │  AustLII │    │  Parser  │    │  (512)   │    │ (Voyage) │  │
│  │  RSS     │    │          │    │          │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │         │
│                                                        ▼         │
│                                               ┌──────────────┐  │
│                                               │    Qdrant    │  │
│                                               │              │  │
│                                               │ Collections: │  │
│                                               │ - compliance │  │
│                                               │ - strategic  │  │
│                                               │ - industry   │  │
│                                               └──────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    RETRIEVAL PIPELINE                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │  Query   │───▶│  Router  │───▶│  Search  │───▶│ Reranker │  │
│  │          │    │          │    │  Qdrant  │    │          │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                        │         │
│                                                        ▼         │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐  │
│  │ Response │◀───│   LLM    │◀───│ Context  │◀───│ Filtered │  │
│  │          │    │ (Claude) │    │ Builder  │    │  Chunks  │  │
│  └──────────┘    └──────────┘    └──────────┘    └──────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Decision Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| **Vector DB** | Qdrant | Already in stack, excellent multi-tenancy, metadata filtering |
| **Embedding Model** | Voyage-3.5-lite | Best RAG accuracy/cost, trained on tricky negatives |
| **Embedding Dimensions** | 512 | Sufficient for domain, lower storage/latency |
| **Collection Strategy** | 3 main collections | compliance, strategic, industry - with namespaces |
| **Primary Sources** | ATO + AustLII | Authoritative, comprehensive, accessible |
| **Update Frequency** | Daily RSS, Weekly full | Balance freshness vs load |

---

## 8. Expanded Content for SMBs, Sole Traders & Tradespeople

### 8.1 Target Audience Profile

Our primary end users are **NOT accountants** - they are:

| Segment | Characteristics | Key Needs |
|---------|-----------------|-----------|
| **Sole Traders** | Individual TFN, no asset protection, personal liability | Simple compliance, deduction maximization |
| **Tradespeople** | Construction, electrical, plumbing, carpentry | Tool deductions, vehicle, contractor vs employee |
| **SMBs** | Company or trust structure, 1-20 employees | Payroll, super, BAS, growth planning |
| **Service Businesses** | Consultants, freelancers, coaches | Home office, travel, ABN/GST |

### 8.2 Business Advisory Content (Beyond Tax)

The AI agents serving business owners need knowledge beyond compliance:

```
EXPANDED STRATEGIC COLLECTION
═══════════════════════════════════════════════════════════════════

┌─────────────────────────────────────────────────────────────────┐
│                 BUSINESS FUNDAMENTALS                            │
│                 (business_fundamentals)                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces:                                                     │
│  ├── starting_business        # ABN, registration, structure    │
│  ├── business_planning        # Business plans, forecasting     │
│  ├── pricing_strategy         # Pricing models, margins         │
│  ├── marketing_basics         # Customer acquisition            │
│  └── legal_essentials         # Contracts, insurance, liability │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 FINANCIAL MANAGEMENT                             │
│                 (financial_management)                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces:                                                     │
│  ├── cash_flow_management     # Cash flow 101, forecasting      │
│  ├── debtor_management        # Chasing invoices, payment terms │
│  ├── expense_management       # Cost control, budgeting         │
│  ├── pricing_profitability    # Margin analysis, breakeven      │
│  └── financial_health         # Ratios, benchmarks, KPIs        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                 PEOPLE & OPERATIONS                              │
│                 (people_operations)                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Namespaces:                                                     │
│  ├── hiring_first_employee    # Employment basics, awards       │
│  ├── contractor_management    # Contractor vs employee          │
│  ├── payroll_basics           # Super, PAYG withholding         │
│  ├── workplace_safety         # WHS, insurance                  │
│  └── scaling_team             # When/how to hire                │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 8.3 Additional Content Sources for Business Advisory

| Source | Content Type | Priority |
|--------|--------------|----------|
| [Business.gov.au](https://business.gov.au) | Official government business guides | P1 |
| [SBDC](https://www.smallbusiness.wa.gov.au) | Small Business Development Corporation | P1 |
| [ASIC Small Business](https://asic.gov.au/for-business/small-business/) | Compliance, director duties | P1 |
| [NSW Small Business Commissioner](https://www.smallbusiness.nsw.gov.au) | State-specific guidance | P2 |
| [Fair Work Ombudsman](https://www.fairwork.gov.au) | Employment, awards, wages | P1 |
| [SafeWork Australia](https://www.safeworkaustralia.gov.au) | WHS requirements | P2 |
| [NAB/CBA/ANZ Business Guides](https://www.nab.com.au/business/small-business) | Practical business advice | P3 |

### 8.4 Trades-Specific Knowledge

For tradespeople (electricians, plumbers, builders, etc.):

| Topic | Content | Source |
|-------|---------|--------|
| **Tool Deductions** | What's claimable, depreciation, instant write-off | ATO |
| **Vehicle Claims** | Logbook vs cents-per-km, ute rules | ATO |
| **Uniform/PPE** | Safety gear, high-vis, boots | ATO |
| **Travel** | Site-to-site, overnight, LAFHA | ATO |
| **Licensing** | State licensing requirements, renewals | State regulators |
| **Insurance** | Public liability, professional indemnity, workers comp | Industry guides |
| **Contractor Rules** | PSI, personal services income, Part IVA | ATO |
| **Subbie Management** | Taxable payments reporting, TPAR | ATO |

---

## 9. Hybrid Retrieval Architecture: PostgreSQL + Qdrant

### 9.1 The Challenge

We have two data stores that must work together for the "Magic Zone":

| Data Store | Contains | Purpose |
|------------|----------|---------|
| **PostgreSQL** | Client data (Pillar 1) - revenue, transactions, entity type, industry, BAS history | Personalization context |
| **Qdrant** | Knowledge (Pillars 2 & 3) - compliance rules, strategic advice | Authoritative answers |

**The Magic happens when we combine them:**
- User asks: "What deductions can I claim?"
- We need to know: Their industry, entity type, revenue level, existing expenses
- Then filter knowledge: Relevant deductions for construction sole trader with $180K revenue

### 9.2 Context Injection Architecture

```
HYBRID RETRIEVAL FLOW
═══════════════════════════════════════════════════════════════════

     USER QUERY: "What deductions am I missing?"
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT ENRICHMENT                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  1. IDENTIFY CONTEXT                                             │
│     ├── tenant_id (from auth)                                   │
│     ├── connection_id (which client)                            │
│     └── user_role (accountant or business owner)                │
│                                                                  │
│  2. FETCH CLIENT PROFILE (PostgreSQL - single query)            │
│     SELECT                                                       │
│       c.organization_name,                                       │
│       c.industry_code,           -- ANZSIC code                 │
│       c.entity_type,             -- sole_trader, company, trust │
│       c.gst_registered,                                          │
│       c.annual_revenue,          -- from synced data            │
│       c.employee_count,                                          │
│       ARRAY_AGG(DISTINCT expense_categories) as claimed_cats    │
│     FROM xero_connections c                                      │
│     LEFT JOIN transactions t ON ...                              │
│     WHERE c.id = :connection_id                                  │
│                                                                  │
│  3. BUILD FILTER CRITERIA                                        │
│     {                                                            │
│       "entity_types": ["sole_trader"],                          │
│       "industries": ["construction_30-32"],                     │
│       "revenue_bracket": "75k-500k"                             │
│     }                                                            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    KNOWLEDGE RETRIEVAL                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  4. SEARCH QDRANT WITH FILTERS                                   │
│                                                                  │
│     search_params = {                                            │
│       "query_vector": embed("deductions missing"),              │
│       "filter": {                                                │
│         "must": [                                                │
│           {"key": "entity_types", "match": {"any": ["sole_trader"]}},│
│           {"key": "industries", "match": {"any": ["construction"]}}  │
│         ]                                                        │
│       },                                                         │
│       "limit": 20                                                │
│     }                                                            │
│                                                                  │
│  5. SEARCH MULTIPLE COLLECTIONS                                  │
│     ├── compliance_knowledge (deductions namespace)             │
│     ├── industry_knowledge (construction namespace)             │
│     └── strategic_advisory (tax_optimization namespace)         │
│                                                                  │
│  6. RERANK COMBINED RESULTS                                      │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CONTEXT ASSEMBLY                              │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  7. BUILD LLM PROMPT                                             │
│                                                                  │
│     <client_context>                                             │
│     Business: ABC Electrical Services                            │
│     Structure: Sole Trader                                       │
│     Industry: Electrical Contracting (ANZSIC 32320)              │
│     GST Registered: Yes                                          │
│     Annual Revenue: $185,000                                     │
│     Employees: 0 (subcontractors used)                           │
│                                                                  │
│     Currently Claimed Deductions:                                │
│     - Vehicle fuel: $8,400                                       │
│     - Materials: $45,000                                         │
│     - Subcontractor payments: $32,000                            │
│     - Insurance: $3,200                                          │
│     - Phone: $1,800                                              │
│                                                                  │
│     NOT Currently Claimed:                                       │
│     - Vehicle depreciation                                       │
│     - Tool depreciation                                          │
│     - Home office                                                │
│     - Safety gear/PPE                                            │
│     - Training/licensing                                         │
│     </client_context>                                            │
│                                                                  │
│     <relevant_knowledge>                                         │
│     [Top 10-15 chunks from Qdrant search]                        │
│     </relevant_knowledge>                                        │
│                                                                  │
│     <question>                                                   │
│     What deductions am I missing?                                │
│     </question>                                                  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                           │
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    LLM RESPONSE                                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  "Based on your electrical contracting business, here are        │
│   deductions you're likely missing:                              │
│                                                                  │
│   1. VEHICLE DEPRECIATION - HIGH PRIORITY                        │
│      You're claiming $8,400 in fuel but no vehicle depreciation. │
│      Estimated additional claim: $3,000-5,000/year               │
│      [Source: ATO - Motor vehicle expenses]                      │
│                                                                  │
│   2. TOOL DEPRECIATION - HIGH PRIORITY                           │
│      No tool expenses recorded. Typical for electricians:        │
│      $4,000-8,000/year in tools and equipment.                   │
│      [Source: ATO - Tools and equipment]                         │
│                                                                  │
│   ..."                                                           │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### 9.3 Efficiency Strategies

| Strategy | Implementation | Benefit |
|----------|----------------|---------|
| **Client Profile Cache** | Cache client context in Redis (TTL: 15 min) | Avoid repeated PostgreSQL queries |
| **Pre-computed Filters** | Store client's filter criteria on sync | Instant Qdrant filter construction |
| **Parallel Retrieval** | Query multiple Qdrant collections in parallel | Reduce latency |
| **Smart Collection Routing** | Only query relevant collections based on query type | Fewer searches |
| **Materialized Views** | Pre-aggregate client profile data in PostgreSQL | Faster context fetch |
| **Batch Context Fetch** | For workboard scenarios, batch fetch multiple clients | N+1 prevention |

### 9.4 Service Layer Design

```python
# backend/app/modules/ai/context_service.py

class ContextService:
    """Builds rich context for AI queries by combining PostgreSQL + Qdrant."""

    def __init__(self, db: AsyncSession, qdrant: QdrantClient, redis: Redis):
        self.db = db
        self.qdrant = qdrant
        self.redis = redis

    async def get_client_context(self, connection_id: UUID) -> ClientContext:
        """Fetch client profile from PostgreSQL (with caching)."""

        # Check cache first
        cache_key = f"client_context:{connection_id}"
        cached = await self.redis.get(cache_key)
        if cached:
            return ClientContext.model_validate_json(cached)

        # Fetch from PostgreSQL
        context = await self._fetch_client_profile(connection_id)

        # Cache for 15 minutes
        await self.redis.setex(cache_key, 900, context.model_dump_json())

        return context

    async def build_qdrant_filters(self, context: ClientContext) -> dict:
        """Convert client context into Qdrant filter criteria."""

        return {
            "must": [
                {"key": "entity_types", "match": {"any": [context.entity_type]}},
            ],
            "should": [
                {"key": "industries", "match": {"any": [context.industry_code]}},
                {"key": "revenue_bracket", "match": {"value": context.revenue_bracket}},
            ]
        }

    async def search_knowledge(
        self,
        query: str,
        context: ClientContext,
        collections: list[str] | None = None
    ) -> list[KnowledgeChunk]:
        """Search Qdrant with client-specific filters."""

        filters = await self.build_qdrant_filters(context)
        query_vector = await self.embed(query)

        # Default collections based on query type
        if collections is None:
            collections = self._route_collections(query)

        # Search all collections in parallel
        results = await asyncio.gather(*[
            self.qdrant.search(
                collection_name=collection,
                query_vector=query_vector,
                query_filter=filters,
                limit=10
            )
            for collection in collections
        ])

        # Flatten and rerank
        all_chunks = [chunk for result in results for chunk in result]
        return await self.rerank(query, all_chunks, limit=15)

    async def build_ai_context(
        self,
        query: str,
        connection_id: UUID
    ) -> AIContext:
        """Complete context assembly for LLM prompt."""

        # Parallel fetch
        client_context, knowledge_chunks = await asyncio.gather(
            self.get_client_context(connection_id),
            self.search_knowledge(query, await self.get_client_context(connection_id))
        )

        return AIContext(
            client=client_context,
            knowledge=knowledge_chunks,
            query=query
        )
```

### 9.5 Database Schema Additions

To support efficient context fetching, add to PostgreSQL:

```sql
-- Materialized view for client AI context
CREATE MATERIALIZED VIEW client_ai_context AS
SELECT
    xc.id as connection_id,
    xc.tenant_id,
    xc.organization_name,
    xc.industry_code,
    xc.entity_type,
    xc.gst_registered,
    COALESCE(rev.annual_revenue, 0) as annual_revenue,
    COALESCE(emp.employee_count, 0) as employee_count,
    COALESCE(exp.expense_categories, '{}') as claimed_expense_categories,
    -- Pre-compute revenue bracket for Qdrant filtering
    CASE
        WHEN rev.annual_revenue < 75000 THEN 'under_75k'
        WHEN rev.annual_revenue < 500000 THEN '75k_to_500k'
        WHEN rev.annual_revenue < 2000000 THEN '500k_to_2m'
        ELSE 'over_2m'
    END as revenue_bracket
FROM xero_connections xc
LEFT JOIN LATERAL (
    SELECT SUM(amount) as annual_revenue
    FROM xero_invoices
    WHERE connection_id = xc.id
    AND date >= NOW() - INTERVAL '12 months'
) rev ON true
LEFT JOIN LATERAL (
    SELECT COUNT(DISTINCT id) as employee_count
    FROM xero_employees
    WHERE connection_id = xc.id
    AND is_active = true
) emp ON true
LEFT JOIN LATERAL (
    SELECT ARRAY_AGG(DISTINCT category) as expense_categories
    FROM xero_transactions
    WHERE connection_id = xc.id
    AND date >= NOW() - INTERVAL '12 months'
    AND amount < 0
) exp ON true;

-- Refresh on Xero sync
CREATE INDEX idx_client_ai_context_connection ON client_ai_context(connection_id);
CREATE INDEX idx_client_ai_context_tenant ON client_ai_context(tenant_id);
```

### 9.6 Performance Targets

| Metric | Target | How |
|--------|--------|-----|
| **Context fetch** | < 50ms | Redis cache + materialized view |
| **Qdrant search** | < 100ms | Parallel collection queries |
| **Total latency** | < 500ms | Efficient pipeline |
| **Cache hit rate** | > 80% | 15-min TTL on client context |

---

## 10. Updated Collection Structure (Final)

```
COMPLETE QDRANT COLLECTIONS
═══════════════════════════════════════════════════════════════════

1. compliance_knowledge      # Tax rules, ATO guidance
   ├── gst
   ├── income_tax
   ├── superannuation
   ├── payroll
   ├── fbt
   ├── rulings
   └── legislation

2. strategic_advisory        # Tax optimization, planning
   ├── entity_structure
   ├── tax_optimization
   ├── cash_flow
   ├── growth_strategy
   └── industry_playbooks

3. industry_knowledge        # Industry-specific content
   ├── construction
   ├── retail
   ├── hospitality
   ├── professional_services
   ├── healthcare
   ├── transport
   └── trades (electrical, plumbing, etc.)

4. business_fundamentals     # General business advice [NEW]
   ├── starting_business
   ├── business_planning
   ├── pricing_strategy
   ├── marketing_basics
   └── legal_essentials

5. financial_management      # Non-tax financial skills [NEW]
   ├── cash_flow_management
   ├── debtor_management
   ├── expense_management
   ├── pricing_profitability
   └── financial_health

6. people_operations         # HR, hiring, compliance [NEW]
   ├── hiring_first_employee
   ├── contractor_management
   ├── payroll_basics
   ├── workplace_safety
   └── scaling_team
```

---

## 11. Next Steps

1. **Create spec.md** - Define user stories for knowledge base
2. **Create plan.md** - Technical architecture and implementation plan
3. **Create tasks.md** - Breakdown into implementable tasks

---

## Sources

### ATO & Legislation
- [ATO RSS Feeds Index](https://www.ato.gov.au/law/view/rss/index.htm)
- [ATO News Feeds](https://www.ato.gov.au/RSS-news-feeds.aspx)
- [CA ANZ ATO Rulings](https://charteredaccountantsanz.com/member-services/technical/tax/tax-in-focus/2024-ato-rulings)
- [AustLII](https://www.austlii.edu.au)
- [legaldata Python Package](https://github.com/dylanhogg/legaldata)

### Vector Database Comparison
- [pgvector vs Qdrant Comprehensive Comparison](https://www.myscale.com/blog/comprehensive-comparison-pgvector-vs-qdrant-performance-vector-database-benchmarks/)
- [Qdrant vs pgvector - Zilliz](https://zilliz.com/comparison/qdrant-vs-pgvector)
- [Pgvector vs Qdrant - Timescale](https://medium.com/timescale/pgvector-vs-qdrant-open-source-vector-database-comparison-f40e59825ae5)
- [Best Vector Databases 2025](https://www.firecrawl.dev/blog/best-vector-databases-2025)

### Multi-Tenancy RAG
- [Multi-Tenancy RAG with Milvus](https://milvus.io/blog/build-multi-tenancy-rag-with-milvus-best-practices-part-one.md)
- [Multi-Tenancy in Pinecone](https://www.pinecone.io/learn/series/vector-databases-in-production-for-busy-engineers/vector-database-multi-tenancy/)
- [Building Multi-Tenant RAG with PostgreSQL](https://www.tigerdata.com/blog/building-multi-tenant-rag-applications-with-postgresql-choosing-the-right-approach)

### Embedding Models
- [Text Embedding Models Compared](https://document360.com/blog/text-embedding-model-analysis/)
- [13 Best Embedding Models 2025](https://elephas.app/blog/best-embedding-models)
- [Best Embedding Models for RAG](https://greennode.ai/blog/best-embedding-models-for-rag)
- [Embedding Models Rundown - Pinecone](https://www.pinecone.io/learn/series/rag/embedding-models-rundown/)

### Hybrid RAG Architecture
- [Building Contextual RAG Systems with Hybrid Search and Reranking](https://www.analyticsvidhya.com/blog/2024/12/contextual-rag-systems-with-hybrid-search-and-reranking/)
- [RAG in 2025: Enterprise Guide](https://datanucleus.dev/rag-and-agentic-ai/what-is-rag-enterprise-guide-2025)
- [pgai - PostgreSQL as AI Retrieval Engine](https://www.blog.brightcoding.dev/2025/08/30/pgai-transforming-postgresql-into-a-production-ready-ai-retrieval-engine-for-rag-applications/)

### Business Advisory Sources
- [Business.gov.au](https://business.gov.au)
- [ASIC Small Business](https://asic.gov.au/for-business/small-business/)
- [Fair Work Ombudsman](https://www.fairwork.gov.au)
- [SBDC - Small Business Development Corporation](https://www.smallbusiness.wa.gov.au)
- [NAB Small Business Guide](https://www.nab.com.au/business/small-business/sole-trader-resource-centre)
