# Research: Comprehensive Australian Tax Knowledge Base

**Feature**: 045-comprehensive-tax-knowledge-base
**Date**: 2026-03-05
**Status**: Complete

---

## 1. Source Inventory

### 1.1 ATO Website (ato.gov.au)

**Copyright**: Permissive Commonwealth license -- "free to copy, adapt, modify, transmit and distribute" with one restriction: no implied ATO endorsement.

**Scraping feasibility**: Highly feasible.
- robots.txt only blocks `/workarea/`, `/widgets/`, `/PrintFriendly.aspx`, `/misc/`
- No crawl-delay specified
- Sitecore CMS, server-rendered HTML
- Legal Database print URLs provide cleanest HTML: `/law/view/print?DocID={TYPE}/{ID}/NAT/ATO/00001&PiT=99991231235958`
- Main site sitemap: ~1,075 URLs

**Content types and estimated volumes**:

| Type | Code/Prefix | Est. Count | Priority |
|------|------------|-----------|----------|
| Taxation Rulings | TR / TXR | ~200-300 | CRITICAL |
| Taxation Determinations | TD / TXD | ~500-600 | CRITICAL |
| GST Rulings | GSTR / GST | ~80-100 | CRITICAL |
| GST Determinations | GSTD | ~50-80 | CRITICAL |
| Class Rulings | CR / CLR | ~1,500-2,000 | HIGH |
| Product Rulings | PR / PRR | ~500-1,000 | MEDIUM |
| Law Companion Rulings | LCR / COG | ~30-50 | HIGH |
| Practical Compliance Guidelines | PCG / COG | ~70-80 | HIGH |
| Miscellaneous Tax Rulings | MT | ~100-150 | MEDIUM |
| Taxpayer Alerts | TA / TPA | ~80-100 | HIGH |
| ATO Interpretative Decisions | ATO ID / AID | ~2,000-3,000 | MEDIUM |
| Practice Statements | PS LA / PSR | ~100-150 | HIGH |
| Decision Impact Statements | DIS | ~100-200 | MEDIUM |
| SMSF Regulator's Bulletins | SRB | ~10-20 | MEDIUM |
| Precedential ATO Guides | SAV | ~32 | CRITICAL |
| Main Website Guidance Pages | N/A | ~1,000-2,000 | HIGH |
| **Total (excl. Edited Private Advice)** | | **~6,500-10,000** | |

**Update frequency**: New rulings published weekly (2:00 PM AEDT). RSS feeds refresh 5x daily. Legal Database updated weekly.

**RSS feeds available**: Taxation Rulings/Determinations, GST Rulings/Determinations, Superannuation Rulings/Determinations.

**Key URL patterns**:
- Print view: `https://www.ato.gov.au/law/view/print?DocID={docid}&PiT=99991231235958`
- Section-level legislation: `https://www.ato.gov.au/law/view/document?docid=PAC/19970038/{section}`
- BAS guides: `https://www.ato.gov.au/businesses-and-organisations/preparing-lodging-and-paying/business-activity-statements-bas`

---

### 1.2 Federal Register of Legislation (legislation.gov.au)

**Copyright**: CC BY 4.0 -- free to share, adapt, use commercially. Attribution required: "Based on content from the Federal Register of Legislation at [date]."

**Scraping feasibility**: Feasible with constraints.
- robots.txt: All content allowed except `/assets/`. **10-second crawl delay required.**
- No public API (unlike Queensland/NSW).
- Best format: **EPUB** (HTML inside ZIP, structured with TOC and anchor IDs).
- URL pattern: `https://www.legislation.gov.au/{ACT_ID}/latest/text/original/epub/OEBPS/document_1/document_1.html`
- Sitemap contains only 29 top-level URLs (not useful for discovery).

**Key tax legislation identifiers**:

| Act | ID | Volumes |
|-----|-----|---------|
| Income Tax Assessment Act 1997 | C2004A05138 | 3+ PDF |
| Income Tax Assessment Act 1936 | C1936A00027 | 6+ PDF |
| A New Tax System (GST) Act 1999 | C2004A00446 | 1-2 |
| Fringe Benefits Tax Assessment Act 1986 | C2004A03280 | 1 |
| Superannuation Guarantee (Admin) Act 1992 | C2004A04402 | 1 |
| Taxation Administration Act 1953 | C1953A00001 | 2+ |
| Tax Agent Services Act 2009 | C2009A00013 | 1 |

**Versioning**: Full point-in-time access. New compilations on every amendment. ITAA 1997 has had 260+ compilations.

**Volume**: ITAA 1997 alone is 5,000-7,000+ pages, ~3,000+ sections. Total estimated ~6,000+ sections across all key tax acts.

**ATO Legal Database alternative for section-level access**:
- `https://www.ato.gov.au/law/view/document?docid=PAC/19970038/{SECTION_NUMBER}`
- Provides individual sections with point-in-time support (`&PiT=` parameter)
- Avoids downloading entire multi-thousand-page acts

---

### 1.3 Case Law Sources

**AustLII (austlii.edu.au)**: NOT VIABLE.
- Explicitly prohibits scraping, automated access, and ALL AI-related use (training, summarizing, paraphrasing, incorporating into AI outputs).
- robots.txt returns HTTP 410, aggressive bot blocking.
- Would require formal written agreement at their discretion.

**Open Australian Legal Corpus (HuggingFace)**: BEST ALTERNATIVE.
- 232,560 documents, 1.47B tokens, 9.4 GB JSONL
- Licensed CC-BY 4.0 -- explicitly permits AI use
- Sources: Federal Court, High Court, Federal Register of Legislation, NSW/QLD/WA/SA/TAS legislation
- **Gap**: Does NOT include AAT/ART tribunal decisions or ATO rulings
- Created by Umar Butler with direct court permissions
- HuggingFace: `isaacus/open-australian-legal-corpus`
- GitHub: `isaacus-dev/open-australian-legal-corpus-creator`

**Federal Court (fedcourt.gov.au)**: Viable for tax cases.
- Judgments from 1977-present, updated daily
- HTML + Word from 1995+, PDF for 1977-1994
- RSS feed: `https://www.judgments.fedcourt.gov.au/rss/fca-judgments`
- Taxation NPA email notifications available
- Can reproduce in unaltered form with attribution
- Progressively adopting CC licensing

**JADE (jade.io)**: Supplementary source.
- 560,000+ cases, 123,000+ statutes
- Free tier: full-text access, search, daily alerts, basic citator
- API via medium neutral citations: `jade.io/article/[citation]`
- Run by BarNet (not-for-profit)

**High Court (hcourt.gov.au)**: Landmark tax decisions.
- Smaller volume but highest authority
- Download, display, print, reproduce in unaltered form

**AAT/ART Gap**: Tribunal tax decisions are the biggest gap. Only on AustLII (prohibited) or by direct arrangement with ART. Options:
- Seek direct permission from Administrative Review Tribunal
- Monitor ART website for published decisions
- Use JADE free tier for individual access

---

### 1.4 Treasury & TPB

**Treasury (treasury.gov.au)**: Exposure drafts, explanatory memoranda as PDFs. No API. Consultation portal at `consult.treasury.gov.au`.

**TPB (tpb.gov.au)**: Explanatory Papers (TPB(EP)), Information Sheets (TPB(I)), Practice Notes (TPB(PN)). HTML pages, some PDFs. No API.

---

## 2. Legal RAG Best Practices

### 2.1 Chunking Strategies

**Legislation must be chunked along its hierarchical structure, NOT by arbitrary character counts.**

Hierarchy for Australian tax acts:
```
Act -> Part -> Division -> Subdivision -> Section -> Subsection -> Paragraph
```

| Content Type | Chunk Boundary | Optimal Size | Notes |
|-------------|---------------|-------------|-------|
| Legislation sections | Section level | 256-512 tokens | Primary atomic unit. Split at subsection only for very long sections. |
| Definitions | Standalone chunks | 100-300 tokens | Tag as `content_type: "definition"`, link defined terms. |
| ATO Rulings (TR/GSTR) | Section-level within ruling | 400-600 tokens | Keep "Ruling" section as single chunk. Split "Explanations" by paragraph. |
| Taxation Determinations (TD) | Whole document or by numbered para | 400-600 tokens | Often short enough for single chunk. |
| Case law - headnote | Single chunk | Variable | High retrieval priority (summary). |
| Case law - reasoning | By issue/numbered paragraph | 400-600 tokens | Most important for legal analysis. |
| ATO guides | Section-level | 400-600 tokens | More narrative content. |

**Overlap**: 50-100 tokens (not the current 200 chars). Research shows overlap improves recall by up to 14.5% but excessive overlap wastes storage.

**Never split mid-subsection or mid-paragraph** -- legal meaning is destroyed.

### 2.2 Definitions Handling

- Store definitions as standalone chunks with `content_type: "definition"` and `defined_term: "associate"`.
- Create cross-reference graph edges from chunks using defined terms back to definitions.
- During retrieval, automatically pull definition chunks when a section uses defined terms.
- For high-priority terms, embed definition inline as parenthetical in chunk text.

### 2.3 Cross-Reference Preservation

- Parse cross-references during ingestion with regex: `[Ss]ection\s+\d+[-\w]*`, `[Dd]ivision\s+\d+[A-Z]?`
- Store as metadata: `cross_references: ["s109D ITAA1936", "Div 7A ITAA1936"]`
- Build lightweight knowledge graph (PostgreSQL JSONB or separate table) mapping section -> referenced sections
- Include parent hierarchy in every chunk: `act`, `part`, `division`, `subdivision`, `section`

### 2.4 Metadata Schema

```python
# Legislation chunks
{
    "act_name": "Income Tax Assessment Act 1997",
    "act_short_name": "ITAA 1997",
    "act_id": "C2004A05138",
    "part": "3-1",
    "division": "104",
    "subdivision": "104-A",
    "section": "104-10",
    "subsection": "104-10(1)",
    "content_type": "operative_provision",  # definition, example, note, table
    "topic_tags": ["CGT", "disposal", "CGT_event_A1"],
    "compilation_date": "2025-07-01",
    "effective_from": "1997-07-01",
    "last_amended_by": "Treasury Laws Amendment (2024 Measures No. 1) Act 2024",
    "cross_references": ["s104-5", "s110-25", "Div 115"],
    "defined_terms_used": ["CGT asset", "capital proceed", "cost base"],
    "full_section_ref": "s104-10 ITAA 1997",
    "fy_applicable": ["2025", "2026"],
}

# Ruling chunks
{
    "ruling_number": "TR 2024/1",
    "ruling_type": "taxation_ruling",
    "status": "current",
    "superseded_by": None,
    "issue_date": "2024-03-15",
    "related_legislation": ["s109D ITAA 1936", "Div 7A ITAA 1936"],
    "related_rulings": ["TD 2023/4", "PCG 2024/2"],
    "topic_tags": ["division_7a", "loans", "private_company"],
    "entity_types": ["company", "trust"],
    "section_type": "ruling",  # explanation, example, appendix
}

# Case law chunks
{
    "case_name": "Commissioner of Taxation v Bamford",
    "case_citation": "[2010] HCA 10",
    "court": "High Court of Australia",
    "decision_date": "2010-03-30",
    "legislation_considered": ["s97 ITAA 1936", "s101 ITAA 1936"],
    "topic_tags": ["trust_income", "distribution", "present_entitlement"],
    "section_type": "headnote",  # facts, reasoning, orders
    "outcome": "appeal_allowed",
}
```

---

## 3. Retrieval Architecture

### 3.1 Hybrid Search (Essential for Legal Content)

Pure semantic search fails for queries with specific section numbers, ruling numbers, or case citations.

| Query Type | Semantic Only | Hybrid (Semantic + BM25) |
|-----------|--------------|--------------------------|
| "What does section 109D say?" | May miss exact section | BM25 matches "109D" exactly |
| "TR 2024/1 Division 7A" | Broad concept match | BM25 matches ruling number |
| "CGT event A1" | Finds CGT broadly | BM25 matches specific event |

**Domain-Partitioned Hybrid RAG achieves 70% pass rate vs 37.5% for RAG-only** (arxiv 2602.23371).

**Implementation**: Pinecone supports sparse-dense hybrid via sparse vectors. Alternative: maintain separate BM25 index using `rank-bm25` Python library and fuse results with Reciprocal Rank Fusion (RRF).

**Fusion weights**: Start at 0.6 semantic / 0.4 keyword. Dynamically adjust based on query type.

### 3.2 Cross-Encoder Re-ranking

After initial retrieval (top 20-30), re-rank with cross-encoder for final top 5-10.

Recommended: `cross-encoder/ms-marco-MiniLM-L-6-v2` -- raises retrieval accuracy from 65-80% to 85-90%. Adds ~100-200ms latency.

Pipeline: `Query -> Hybrid Search (top 30) -> Cross-Encoder Re-rank (top 10) -> Context Assembly -> LLM`

### 3.3 Query Classification & Routing

Extend existing `intent_detector.py`:

| Query Type | Detection | Retrieval Strategy |
|-----------|-----------|-------------------|
| Direct reference ("s109D") | Regex on section pattern | Keyword-heavy (0.2 sem / 0.8 kw) |
| Conceptual ("Div 7A issue?") | No specific section | Semantic-heavy (0.7 sem / 0.3 kw) + expansion |
| Procedural ("How to lodge BAS?") | Action verbs | Standard hybrid; filter `source_type: "ato_guide"` |
| Scenario ("Client took $50k loan") | Factual description | Semantic + expansion; retrieve legislation + rulings |
| Ruling lookup ("TR 2024/1") | Ruling number pattern | Pure keyword on `ruling_number` metadata |

### 3.4 Query Expansion

Before retrieval, use LLM to expand with legislative synonyms:
- Input: "Does my client have a Div 7A issue?"
- Expanded: "Division 7A Part III ITAA 1936 section 109D 109E 109F loans private company shareholder associate deemed dividend"

Maintain legal term synonym table (e.g., "GST" <-> "Goods and Services Tax" <-> "A New Tax System (Goods and Services Tax) Act 1999").

---

## 4. Hallucination Prevention

### 4.1 Scale of Problem

Stanford study (2025): Lexis+ AI hallucination rate 17%, Westlaw 33%, GPT-4 (no RAG) 43%. Even 17% is unacceptable for tax compliance.

### 4.2 Grounding Architecture

1. **Retrieval-grounded only**: Claude never answers from parametric memory on tax questions. Every response must cite retrieved chunks.
2. **Citation verification**: Post-generation, extract all section/ruling references via regex. Cross-reference against retrieved chunks. Flag ungrounded claims.
3. **Confidence scoring**: `confidence = weighted_avg(top_chunk_score * 0.4, mean_top_5_scores * 0.3, citation_verification_rate * 0.3)`
4. **Decline thresholds**: Top score < 0.5 → decline. 0.5-0.7 → answer with caveats. > 0.7 → answer with citations.
5. **Supersession awareness**: Always flag superseded rulings. Present current position.

### 4.3 Entity Grounding (HalluGraph Framework)

- Verify entities in response (section numbers, case names, amounts) appear in retrieved context.
- Verify relationships stated in response are supported by source text.
- Flag responses that introduce claims beyond context for human review.

---

## 5. Embedding Model Consideration

**Massive Legal Embedding Benchmark (MLEB)** results:

| Model | MLEB NDCG@10 | Notes |
|-------|-------------|-------|
| Kanon 2 Embedder | 86.03% | #1 legal. Australian company (Isaacus). |
| Voyage 3 Large | 85.71% | Close second. |
| Voyage 3.5 | 84.07% | Strong general. |
| voyage-3.5-lite (current) | ~78-80% est. | ~6-8% behind Kanon 2. |

**Recommendation**: Evaluate Kanon 2 Embedder (Australian-made, best legal performance) or Voyage 3 Large as upgrade from current voyage-3.5-lite.

---

## 6. Existing Clairo Infrastructure

### What's Already Built (Reusable)

| Component | Location | Status |
|-----------|----------|--------|
| Pinecone service | `core/pinecone_service.py` | Production-ready |
| Voyage embeddings | `core/voyage.py` | 1024-dim, production |
| 7 knowledge namespaces | `knowledge/collections.py` | Active |
| ATO RSS scraper | `knowledge/scrapers/ato_rss.py` | Working |
| ATO Web scraper | `knowledge/scrapers/ato_web.py` | Framework exists |
| Semantic chunker | `knowledge/chunker.py` | 1500 char, recursive split |
| Document processor | `knowledge/document_processor.py` | PDF, DOCX, TXT |
| Content dedup | `knowledge/models.py` (ContentChunk.content_hash) | SHA-256 |
| Supersession tracking | `knowledge/models.py` (is_superseded, superseded_by) | Manual |
| Ingestion pipeline | `tasks/knowledge.py` | Celery background tasks |
| Knowledge chatbot | `knowledge/chatbot.py` | Streaming, citations |
| Client context chat | `knowledge/client_chatbot.py` | Financial context injection |
| Intent detection | `knowledge/intent_detector.py` | 5 intents |
| Token budget | `knowledge/token_budget.py` | Tiered allocation |
| Evidence traceability | `insights/evidence.py` | Spec 044, Phase 1 complete |
| Citation system | `knowledge/chatbot.py` | Numbered, deduped by URL |

### Key Gaps to Fill

| Gap | Current State | Required |
|-----|--------------|----------|
| Legislation scraper | None | EPUB parser for legislation.gov.au + ATO section-level |
| Case law ingestion | None | Open Australian Legal Corpus + Federal Court RSS |
| Structure-aware chunking | Generic recursive split | Legislation hierarchy parser, ruling section parser |
| Hybrid search | Semantic only (Pinecone) | Add BM25/sparse vectors |
| Cross-encoder re-ranking | None | Post-retrieval re-ranker |
| Query classification | Basic 5 intents | Legal query routing (6+ types) |
| Query expansion | None | LLM-assisted + synonym table |
| Cross-reference graph | None | Section-to-section links (PostgreSQL) |
| Definitions index | None | Standalone definition chunks + auto-injection |
| Automated supersession | Manual only | Parse ATO listings during ingestion |
| Citation verification | None | Post-generation grounding check |
| Content freshness pipeline | Manual ingestion | Scheduled crawlers + RSS monitoring |

---

## 7. Scale Estimates

### Vector Count

| Source | Est. Chunks |
|--------|------------|
| Legislation sections (all key acts) | ~14,000 |
| ATO Rulings (TR, TD, GSTR, GSTD, MT) | ~12,000 |
| Class/Product Rulings | ~20,000 |
| LCR + PCG + TA + PS LA + DIS + SRB | ~5,000 |
| ATO Guidance (website pages) | ~30,000 |
| Precedential Guides (SAV) | ~500 |
| Tax case law (Federal Court + High Court) | ~10,000 |
| Definitions index | ~2,000 |
| **Total** | **~93,500** |

### Resource Requirements

| Resource | Estimate |
|----------|---------|
| Vector storage (Pinecone) | ~1-2 GB with metadata |
| Initial embedding cost | ~40M tokens, ~$4-8 (Voyage) |
| Monthly update embedding | ~5K chunks/month |
| Pinecone cost | ~$10-30/month (serverless, 100K vectors) |
| Query latency target | <500ms (retrieval + re-rank) |
| Re-ranker latency | +100-200ms |

---

## Sources

### Academic & Technical
- SAT-Graph RAG: Ontology-Driven Graph RAG for Legal Norms (arxiv 2505.00039)
- Domain-Partitioned Hybrid RAG for Legal Reasoning (arxiv 2602.23371)
- HalluGraph: Auditable Hallucination Detection for Legal RAG (arxiv 2512.01659)
- LegalBench-RAG: Benchmark for Legal RAG (arxiv 2408.10343)
- Stanford HAI: AI Legal Models Hallucinate (2025)
- Massive Legal Embedding Benchmark (MLEB) -- HuggingFace
- VersionRAG: Version-Aware RAG for Evolving Documents (arxiv 2510.08109)
- Bayesian RAG: Uncertainty-Aware Retrieval (Frontiers, 2025)

### Data Sources
- ATO Legal Database: ato.gov.au/law/
- Federal Register of Legislation: legislation.gov.au (CC BY 4.0)
- Open Australian Legal Corpus: huggingface.co/datasets/isaacus/open-australian-legal-corpus (CC BY 4.0)
- Federal Court Judgments: fedcourt.gov.au/digital-law-library/judgments
- JADE: jade.io
- TPB: tpb.gov.au/policy-and-guidance
- Treasury: treasury.gov.au/consultation

### Tools & Libraries
- Open Australian Legal Corpus Creator: github.com/isaacus-dev/open-australian-legal-corpus-creator
- Kanon 2 Embedder: huggingface.co/blog/isaacus/kanon-2-embedder
- cross-encoder/ms-marco-MiniLM-L-6-v2 (re-ranking)
- rank-bm25 (Python BM25 implementation)
- Inscriptis (HTML to text), mammoth (DOCX to HTML)
