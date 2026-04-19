# Implementation Plan: Tax Strategies Knowledge Base — Phase 1 Infrastructure

**Branch**: `060-tax-strategies-kb` | **Date**: 2026-04-18 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/060-tax-strategies-kb/spec.md`
**Supporting docs**: `docs/tax planning/tax-strategies-architecture.md`, `specs/briefs/2026-04-18-tax-strategies-knowledge-base.md`

## Summary

Phase 1 delivers the **plumbing** for Clairo's reviewer-approved tax strategies corpus: a new `tax_strategies` backend module (TaxStrategy parent + TaxStrategyAuthoringJob tables), two additive nullable columns on `ContentChunk`, a new `StrategyChunker`, multi-namespace + structured-eligibility retrieval extensions, a new `tax_strategies` Pinecone namespace (shared), a `[CLR-XXX: Name]` citation extension in `CitationVerifier`, an admin "Strategies" tab shell (list + detail view + pipeline dashboard + stage-action buttons), the CSV-backed idempotent bulk-seed action for the 415 stubs, and a `StrategyChip` frontend component that renders verified/partially-verified/unverified citations in tax planning chat.

The Phase 1 exit criterion is **one strategy end-to-end** — a super-admin can advance a stub through research → draft → enrich → submit → approve → publish and then see the resulting strategy cited as a green `[CLR-XXX: Name]` chip in tax planning chat. Full content authoring of the 415 strategies is out of scope (Phase 2).

**Governing constraint**: vectors are written **once, in production**. Publish is gated on the env flag `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default false). Non-production environments read from the shared namespace and never write to it.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 App Router + React 18 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0 async, Pydantic v2, Alembic, Celery + Redis, Anthropic SDK (Claude Sonnet for research/draft/enrich tasks), Voyage 3.5 lite via `VoyageService` (embeddings), Pinecone via `PineconeService`, shadcn/ui (Sheet, Dialog, Table, Badge)
**Storage**: PostgreSQL 16 — 2 new tables (`tax_strategies`, `tax_strategy_authoring_jobs`); 2 new nullable columns on existing `content_chunks` (`tax_strategy_id` FK, `chunk_section`, `context_header`); 1 new Pinecone namespace (`tax_strategies`, shared); 1 new in-repo CSV fixture (`backend/app/modules/tax_strategies/data/strategy_seed.csv`, 415 rows)
**Testing**: pytest + pytest-asyncio (backend unit + integration), factory_boy for fixtures, Jest + React Testing Library (frontend unit), Playwright for vertical-slice E2E covering the quickstart walkthrough
**Target Platform**: Existing Clairo deployment (AWS Sydney for backend, Vercel for frontend). Phase 1 changes run in all environments; vector writes only in prod via env flag.
**Project Type**: web (modular monolith backend + Next.js frontend) — follows constitution §I module layout
**Performance Goals**: Retrieval latency p95 ≤ 800ms end-to-end for tax planning chat when `tax_strategies` namespace is included (architecture §19.4). Admin Strategies tab list ≤ 500ms for 500 rows. Publish action p95 ≤ 30s per strategy. No perceptible regression on existing retrieval callers when `tax_strategies` namespace is empty (SC-004).
**Constraints**: Single-writer invariant on the shared vector namespace — only prod writes. Partial-publish failures leave strategy in `approved` with a failed job row, never half-published (FR-011). `tenant_id` always present in pinecone filter and SQL queries. `source_ref` never surfaces to any end user (FR-008). Local dev path exercises the pipeline against a 3–5 strategy fixture without touching production (FR-030).
**Scale/Scope**: 415 parent rows × 2 chunks = ~830 vectors at full coverage. Phase 1 ships with 415 stubs + at most a handful of fully-published fixtures. Admin list paginates for 415 rows (not a scale concern).

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|---|---|---|
| I. Modular monolith — module boundaries | PASS | New module `backend/app/modules/tax_strategies/` with `router.py`, `service.py`, `schemas.py`, `models.py`, `repository.py`, `exceptions.py`. Cross-module calls via `KnowledgeService` only; never reaches into `knowledge.repository` directly. |
| II. Technology stack | PASS | Uses approved stack (FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK, Voyage 3.5 lite, Pinecone, shadcn/ui). No new dependencies. |
| III. Repository pattern | PASS | `TaxStrategyRepository` encapsulates all DB access. Service layer raises domain exceptions from `exceptions.py`; router converts to HTTPException. Uses `flush()` not `commit()`. |
| IV. Multi-tenancy | PASS | `tenant_id` on `tax_strategies` (default `"platform"`). Retrieval filter always unions `{"platform", <tenant_uuid>}` (§9.2 arch). Phase 1 exercises `"platform"` only; overlay deferred to Phase 3 per spec Assumption. |
| V. Testing strategy | PASS | Unit + integration + E2E coverage per §19.1. CI-gated. Local 3–5 strategy fixture path (FR-030) satisfies the developer test story. |
| VI. Code quality | PASS | Type hints + Pydantic v2 strict + Ruff + mypy enforced on new module. |
| VII. API design | PASS | RESTful admin endpoints under `/api/v1/admin/tax-strategies/...`. Generated OpenAPI surfaced to frontend via `openapi-typescript`. |
| VIII. External integrations | PASS | LLM drafting is research/draft/enrich only. All LLM outputs pass through reviewer sign-off before publish; no LLM output reaches the retrieval corpus without human approval (HITL, constitution §VIII and §XI). Publish step is deterministic — chunk + embed + upsert, no LLM. |
| IX. Security | PASS | Admin surfaces gated on Clerk `super_admin` role (existing pattern in `admin/knowledge/page.tsx`). Public hydration endpoint (`GET /tax-strategies/{id}/public`) returns only non-internal fields; never `source_ref`. |
| X. Auditing (first-class) | PASS | Spec §Audit Events section enumerates 6 event types covering all lifecycle transitions + seed. Uses existing `app.core.audit.audit_event()` pattern. Integration tests assert audit rows per §19.1. |
| XI. AI/RAG human-in-the-loop | PASS | LLM drafts never enter retrieval directly — reviewer approval is a blocking gate between `enriched` and `approved`. Phase 2 content arrangement is explicit about paid reviewer. |
| XII. Spec-kit workflow | PASS | This `plan.md` is the `/speckit.plan` output for `060-tax-strategies-kb`. Tasks follow in `tasks.md`. |

**Gate result**: PASS. No constitutional violations. No entries in Complexity Tracking.

## Project Structure

### Documentation (this feature)

```text
specs/060-tax-strategies-kb/
├── plan.md              # This file
├── spec.md              # Feature spec (with clarifications)
├── research.md          # Phase 0 output (this command)
├── data-model.md        # Phase 1 output (this command)
├── quickstart.md        # Phase 1 output (this command)
├── contracts/           # Phase 1 output (this command)
│   ├── admin-tax-strategies.openapi.yaml
│   ├── public-tax-strategies.openapi.yaml
│   └── knowledge-search-extensions.md
├── checklists/
│   └── requirements.md
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── knowledge/                     # EXTENDED (not replaced)
│   │   │   ├── collections.py             # + NAMESPACES["tax_strategies"] (shared=True)
│   │   │   ├── models.py                  # + ContentChunk.tax_strategy_id, chunk_section, context_header
│   │   │   ├── schemas.py                 # + namespaces, structured-eligibility fields on KnowledgeSearchRequest/Filters
│   │   │   ├── service.py                 # pass-through namespaces to HybridSearchEngine
│   │   │   ├── chunkers/
│   │   │   │   └── strategy.py            # NEW — StrategyChunker(BaseStructuredChunker)
│   │   │   └── retrieval/
│   │   │       ├── citation_verifier.py   # + [CLR-XXX: Name] extractor + verify_strategy_citations()
│   │   │       └── hybrid_search.py       # already supports multi-namespace; no structural change
│   │   └── tax_strategies/                # NEW MODULE
│   │       ├── __init__.py
│   │       ├── models.py                  # TaxStrategy, TaxStrategyAuthoringJob
│   │       ├── schemas.py                 # Pydantic request/response schemas
│   │       ├── repository.py              # All DB access
│   │       ├── service.py                 # Lifecycle transitions, seed, verify-on-publish
│   │       ├── router.py                  # Admin + public endpoints
│   │       ├── exceptions.py              # Domain exceptions
│   │       ├── audit_events.py            # 6 event types per spec
│   │       ├── env_gate.py                # TAX_STRATEGIES_VECTOR_WRITE_ENABLED check
│   │       └── data/
│   │           └── strategy_seed.csv      # 415 rows: strategy_id,name,categories,source_ref
│   ├── tasks/
│   │   └── tax_strategy_authoring.py      # NEW — Celery research/draft/enrich/publish
│   └── alembic/versions/
│       └── 2026xxxx_tax_strategies_phase1.py   # NEW migration
├── tests/
│   ├── unit/modules/tax_strategies/
│   │   ├── test_strategy_chunker.py
│   │   ├── test_citation_verifier_clr.py
│   │   ├── test_service_lifecycle.py
│   │   ├── test_env_gate.py
│   │   └── test_seed_idempotent.py
│   └── integration/
│       ├── test_publish_roundtrip.py      # publish → ContentChunk + BM25 + Pinecone populated
│       ├── test_retrieval_multi_namespace.py
│       └── test_api_tax_strategies.py
└── pyproject.toml                         # no new deps

frontend/
├── src/
│   ├── app/(protected)/admin/knowledge/
│   │   ├── page.tsx                       # + Strategies tab registration
│   │   ├── components/
│   │   │   ├── strategies-tab.tsx         # NEW — list + filters + counters
│   │   │   ├── strategy-detail-sheet.tsx  # NEW — read-only fields + action bar
│   │   │   └── strategies-pipeline.tsx    # NEW — kanban dashboard
│   │   └── hooks/
│   │       └── use-tax-strategies.ts      # NEW — TanStack Query hooks
│   └── components/tax-planning/
│       ├── CitationBadge.tsx              # EXTENDED — counts strategy citations
│       ├── StrategyChip.tsx               # NEW — inline clickable chip
│       ├── StrategyDetailSheet.tsx        # NEW — Sheet for chip click
│       └── useStrategyHydration.ts        # NEW — hydrate full strategy by id list
└── tests/
    ├── components/tax-planning/strategy-chip.test.tsx
    └── admin/strategies-tab.test.tsx
```

**Structure Decision**: Web-application layout, extending the existing modular monolith. New module `tax_strategies` follows constitution §I module template exactly. Knowledge module is **extended additively** — no existing field renamed, no existing signature broken. Frontend adds a fourth admin tab ("Strategies") and a small set of chat-layer components. No changes to `tax_planning` module's public surface — only its single retrieval hook (`_retrieve_tax_knowledge`) gets new kwargs with backwards-compatible defaults.

## Complexity Tracking

*No constitutional violations — section intentionally empty.*
