# Brief: Tax Strategies Knowledge Base

**Date**: 2026-04-18
**Source**: Follow-up from Unni's alpha feedback on tax planning (Zac & Angela Phillpott session, 2026-04-18). Unni shared the Tax Fitness strategy library (415 entries across 8 categories, STP-branded) as a reference for how accountants already think about strategy coverage. Context also draws on the UX journey proposal and the Tax Fitness content sample (see `/Users/suren/Documents/Claude/Projects/Clairo/` folder).
**Author**: Suren (product) + Claude design pass after codebase audit of `backend/app/modules/knowledge/*` and frontend `app/(protected)/admin/knowledge/*`
**Related briefs**: `2026-04-18-tax-planning-calculation-correctness.md` (calc correctness), `2026-04-18-tax-planning-group-tax-model.md` (multi-entity model). This brief is orthogonal — it addresses the "what strategies are grounded and citable" layer under the tax planning chat + scenario generation surfaces.
**Full architecture doc**: `docs/tax planning/tax-strategies-architecture.md` and deliverable at `/Users/suren/Documents/Claude/Projects/Clairo/clairo-tax-strategies-architecture.docx`.

**Status**: Design-pass complete, awaiting Suren/Asaf walk-through and Unni reviewer arrangement before Phase 1 build.

---

## Problem Statement

The tax planning module currently generates strategy suggestions from ungrounded LLM knowledge. In Unni's live alpha session this produced two related trust failures: **unverified citations** (F1-14 — "Sources could not be verified" badges) and **AI-invented baseline numbers** in the Analysis tab (F1-12 — e.g. "$25k prepaid rent" that Unni never confirmed). The underlying issue is that Clairo has no grounded strategy corpus — the model is pulling strategies from training data with no traceable source, so the citation verifier has nothing to verify against.

Unni shared the Tax Fitness strategy library (415 strategies across 8 groups — Business, Recommendations, Employees, ATO obligations, Rental properties, Investors & retirees, Business structures, SMSF) showing exactly the shape of content that would solve this. Each strategy has a consistent 5-section layout: name, category, implementation advice, strategy explanation, indicative dollar figure. The library is authoritative, current to FY25, and includes the exact compliance checks (e.g. #241 "Change PSI to PSB" contains the Results Test + 80% rule that Unni caught manually in Zac's session).

**We cannot ingest Tax Fitness verbatim** — it's STP-branded content (Success Tax Professionals is a national AU accounting franchise; Tax Fitness is their licensed strategy program). Ingesting those specific PDFs for platform-wide, multi-tenant use would bind Clairo to STP's licence terms.

**Solution direction**: build an equivalent Clairo-owned corpus — same coverage (415 strategies, 8 categories, mirrored taxonomy), same structure (4-section shape after dropping the indicative $ figure), but reauthored from ATO primary sources (ITAA, TRs, PS LAs, rulings, case law) with Unni as paid reviewer. Ingest into a new Pinecone namespace `tax_strategies`. Plug into the existing hybrid retrieval stack (BM25 + semantic + RRF + cross-encoder reranker) and citation verifier. Add an admin UI tab alongside the existing knowledge base management surfaces.

---

## Users

- **Primary**: Accountants using Clairo's tax planning feature (Unni, Vik, beta cohort). They need AI strategy suggestions to cite their firm's strategy material verbatim, with ATO source as backing.
- **Secondary**: Super-admins managing the platform-baseline strategy corpus via `/admin/knowledge` (ingestion, review, publishing).
- **Content reviewer**: Unni, under a paid advisory arrangement, reviews each strategy before publication.
- **Later**: Business-owner clients who see citations in the client-facing tax plan summary.

---

## Goals

1. **Trust**: every AI claim traceable to a specific strategy entry (`[CLR-241: Change PSI to PSB]`) and the ATO source behind it. Directly closes F1-14 unverified citations.
2. **Recall**: ≥ 90% top-5 retrieval on a gold-set of accountant queries (built with Unni) for the top-100 strategies.
3. **Precision**: top-5 reranked results are the strategies an accountant would actually cite.
4. **Operability**: admin surfaces follow the existing `/admin/knowledge` tabbed pattern (SourcesTab, JobsTab, CollectionsTab, SearchTestTab); Asaf doesn't invent a new UI and Unni doesn't learn a new tool.
5. **Tenant-ready**: platform baseline today, per-tenant private overlay (Unni's STP library in his own tenant — "Path A") possible later without refactor.

---

## Approach

### Content
- **Coverage**: 1:1 with Tax Fitness (415 strategies, 8 categories, multi-tag).
- **Reauthoring**: tax-law facts preserved verbatim (thresholds, percentages, tests, dates — these are ATO law, not STP IP). Category taxonomy mirrored. Structure mirrored. Prose wording, implementation steps, and scoped commentary written fresh from ATO primary sources.
- **IDs**: Clairo-owned `CLR-001` … `CLR-415`. STP source reference carried internally as metadata only, never surfaced.
- **Indicative $ figure**: dropped. The tax planning calc engine produces real client-specific numbers; the library gives "what to consider and how to implement."

### Architecture (fits existing Clairo knowledge module)
- **New Pinecone namespace** `tax_strategies` added to `NAMESPACES` dict in `collections.py` (shared=true).
- **New module** `backend/app/modules/tax_strategies/` with `TaxStrategy` parent model (authoritative full strategy record). `ContentChunk` gets nullable FK + chunk_section columns; chunks point back to parent.
- **Chunking**: parent-child with contextual headers. Two child chunks per strategy (implementation + explanation), each prefixed with `[CLR-XXX: Name — Category: X]` context header, suffixed with a `Keywords:` line of aliases/shorthand. Full parent returned to LLM.
- **Retrieval extensions**: `KnowledgeSearchRequest.namespaces: list[str]` added (default preserves current behaviour). `KnowledgeSearchFilters` extended with structured eligibility (income_band, turnover_band, age, industry_codes) populated from client context for pre-filtering before semantic search — the single biggest hit-rate lever.
- **Two-pass retrieval**: hybrid search → dedupe chunks by `tax_strategy_id` → cross-encoder rerank on full parent text → top 6–8 returned.
- **Citations**: `[CLR-XXX: Name]` markup. `CitationVerifier` extended to recognise the pattern. New `StrategyChip` frontend component renders inline clickable chip; new `useStrategyHydration` hook fetches full strategy via `GET /tax-strategies/{id}/public`. Extends existing `CitationBadge` message-level summary.

### Admin UI
- New "Strategies" tab in `/admin/knowledge`, mirroring `sources-tab.tsx` pattern. Components in `admin/knowledge/components/strategies-tab.tsx`.
- Strategy list with status filters (stub / researching / drafted / enriched / in_review / approved / published / superseded), category filter, tenant filter.
- Detail Sheet with markdown editor for implementation + explanation, form controls for structured eligibility fields, ATO sources + case refs arrays, version history, authoring jobs log.
- Kanban-style pipeline dashboard with Unni's in-review queue highlighted.
- Collections tab and Search Test tab pick up the new namespace automatically.

### Content authoring pipeline
- Celery-based, modelled on existing `IngestionJob` pattern. New queue `tax_strategies`, new task names `tax_strategies.research | draft | enrich | publish`.
- Stages: stub → researching → drafted → enriched → in_review → approved → published (→ superseded for version rotation).
- Research task pulls ATO primary sources. Draft task uses Claude Sonnet/Opus with strict system prompt (facts from sources only, no invented content, no STP/ChangeGPS branding). Enrich task extracts structured eligibility metadata. Unni reviews each in admin UI; approve triggers chunk → embed (Voyage 3.5 lite) → Pinecone upsert + `ContentChunk` rows + `BM25IndexEntry` rows.
- New table `tax_strategy_authoring_jobs` tracks per-stage jobs.

### Phased rollout
- **Phase 1 (weeks 1–2)**: infrastructure. DB migrations, namespace init, Celery tasks, admin UI shell, citation extensions, seed 415 stub rows. Exit: one strategy end-to-end through the pipeline, retrievable, citable.
- **Phase 2 (weeks 3–8)**: top ~100 strategies authored, enriched, reviewed, published. Unni on paid review (~20/week). Retrieval tuning against Unni-supplied gold-set. Exit: recall ≥ 90% @ top-5, alpha-ready.
- **Phase 3 (weeks 9–16)**: next ~250 strategies. Per-tenant overlay admin (Path A). Exit: ~350 strategies live, beta cohort onboarded.
- **Phase 4 (Q3+)**: long tail + annual ATO-source-change review.

---

## Risks & Mitigations

1. **Unni's review capacity** — 20 approvals/week alongside practice work is ambitious. Paid advisory with explicit weekly review windows; batch LLM drafts; side-by-side review tooling.
2. **LLM draft quality floor** — if >30% rejected, review becomes rewrite. Mitigation: seed 5–10 exemplar strategies Unni writes himself as few-shot examples; monitor rejection rate weekly; prompt tuning.
3. **Structured metadata accuracy** — eligibility filters only work if enrichment pass is right. Default NULL (broadly applicable) when ambiguous; Unni reviews enrichment samples; A/B vs unfiltered baseline for first 50 strategies.
4. **Gold-set construction** — need labelled (query → correct strategies) test set. Unni provides 30–50 real client queries from practice history as paid work; labels populated during review.
5. **Budget/rate volatility** — Stage 3, super caps, thresholds change. Every strategy carries `fy_applicable_from/to` and `ato_sources`; scheduled task refetches ATO content and flags strategies whose source `document_hash` changed.
6. **Rights boundary** — even using Tax Fitness as a coverage list carries some exposure if STP considers the index proprietary. Mitigation: derive coverage from our own reading of AU tax structure (by category); treat Tax Fitness only as completeness sanity-check, not source list.

---

## Open Questions (for Asaf review)

1. Confirm `ContentChunk` nullable column additions fit existing migrations without cascade changes to BM25IndexEntry / ingestion path.
2. Confirm Celery queue `tax_strategies` can be added without worker config changes in dev / staging / prod.
3. Confirm `KnowledgeSearchRequest` adding `namespaces: list[str] | None` is fully backwards-compatible with all existing callers (client_chat, knowledge_chat, tax_planning, insight engine).
4. Confirm the `StrategyChip` + markdown renderer integration point — where in `ScenarioChat.tsx` / chat message renderer does the CLR-XXX tokenizer live?

---

## Success Criteria

Headline measures (full validation plan in architecture doc §19):

- **Coverage**: 100 published strategies by end of Phase 2; 350 by end of Phase 3; 415 at full coverage.
- **Trust**: Unni completes a second live client session (equivalent to Zac's) with zero "Sources could not be verified" badges. Every AI strategy suggestion carries at least one `[CLR-XXX]` citation rendering as a clickable `StrategyChip`.
- **Retrieval quality**: Top-5 recall ≥ 90% on Unni's gold-set; top-1 precision ≥ 60%; PSI sensitivity/specificity thresholds met (see §19.2).
- **Performance**: Retrieval latency p95 ≤ 800ms end-to-end for tax planning chat.
- **Validation layers**: Automated CI tests (§19.1), evaluation benchmarks run weekly during Phase 2 (§19.2), and UAT sign-off by Unni at each phase exit (§19.3). Full definition of done in §19.5.

---

## What to Validate Before Build

1. Walk the full architecture doc with Asaf end-to-end; confirm the ContentChunk extensions and new module fit without breaking existing migrations.
2. Confirm Unni's paid reviewer arrangement (rate, weekly hours, review cadence) so Phase 2 is operational from day one.
3. Build one strategy end-to-end (CLR-012 Concessional super is a good vertical-slice candidate — mid-complexity, high-frequency) as a proof before scaling to 100.
