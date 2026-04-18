# Spec 060 — Handoff

**Status as of 2026-04-19**: Backend wire-complete for the citation pipeline + draft/enrich LLM tasks. Frontend not started. Bulk content authoring not started. `40/77` tasks done (~52%).

---

## Resume checklist (run first in the next session)

```sh
cd /Users/suren/KR8IT/projects/Personal/clairo

# Confirm branch
git rev-parse --abbrev-ref HEAD     # expect: 060-tax-strategies-kb

# Confirm tests still pass from where we left them
cd backend
uv run alembic current               # expect: 060_tax_strategies_phase1 (head)
uv run pytest tests/unit/modules/tax_strategies/ tests/unit/modules/tax_planning/ -q
# expect: 235 passed

uv run ruff check app/modules/tax_strategies app/modules/tax_planning/service.py app/modules/knowledge/retrieval/strategy_hits.py app/modules/knowledge/chunkers/strategy.py
# expect: All checks passed
```

---

## Commits on the branch (in order, oldest first)

1. `7735298` docs(060): spec, briefs, skills (pre-implementation)
2. `85958cc` Phase 1–2 infrastructure — module skeleton, migration, retrieval wiring
3. `66a5bb8` US1 backend slice — StrategyChunker, citation verifier CLR extension, publish task
4. `0a85fe4` Admin + public routers (11 endpoints, Clerk super_admin gate, FR-008 source_ref stripped)
5. `3208fa3` Tax planning retrieval wiring (`<strategy>` envelope, citation plumbing)
6. `98abe5c` US4 seed backend (CSV validator + idempotent loader + endpoint)
7. `5ce1e11` Citation markup normaliser (constitution §VIII code-layer enforcement)
8. `0e2f782` research_strategy fixture-driven ATO sources (T028 partial)
9. `064b04b` Retrieval latency tracer

Each commit is self-contained and compiles/tests independently.

---

## What's in the working tree

### Backend — DONE

- **Module**: `backend/app/modules/tax_strategies/` — models, schemas, repository, service, router, exceptions, audit_events, env_gate, markup, data/ (CSV header + ATO source fixtures)
- **Migration**: `backend/alembic/versions/20260418_060_tax_strategies_phase1.py` applied locally — tables `tax_strategies`, `tax_strategy_authoring_jobs`, plus three nullable columns on `content_chunks`
- **Namespace**: `tax_strategies` added to `NAMESPACES` in `backend/app/modules/knowledge/collections.py` (`shared=True`)
- **Retrieval extensions** (`backend/app/modules/knowledge/schemas.py` + `service.py`):
  - `KnowledgeSearchRequest.namespaces` — opt-in multi-namespace search
  - `KnowledgeSearchFilters` — structured-eligibility fields (income_band, turnover_band, age, industry_codes, tenant_id)
  - FR-017 fallback: strips eligibility clauses and retries when the filter returns zero candidates
  - `KnowledgeSearchResultSchema` carries new nullable strategy fields
- **Two-pass retrieval helper**: `backend/app/modules/knowledge/retrieval/strategy_hits.py` — dedupe by parent + batch fetch + SQL-side supersession filter + cross-encoder rerank on full parent. Not yet wired into `_retrieve_tax_knowledge` (see "gotcha" below).
- **Citation verifier**: `extract_strategy_citations()` + `verify_strategy_citations()` on `CitationVerifier` with three-state classification (verified / partially_verified / unverified) via normalised Levenshtein ≥ 0.30 drift threshold
- **Chunker**: `backend/app/modules/knowledge/chunkers/strategy.py` — two chunks per strategy, context header + keyword tail, paragraph-boundary split
- **Markup normaliser**: `backend/app/modules/tax_strategies/markup.py` — rewrites near-miss CLR forms to canonical `[CLR-XXX: Name]` when the identifier is in the retrieved set; unknown identifiers left alone so the verifier flags them red
- **Celery tasks** (`backend/app/tasks/tax_strategy_authoring.py`):
  - `publish_strategy` — DONE (env-gated, deterministic vector IDs, ContentChunk + BM25IndexEntry written before Pinecone upsert)
  - `research_strategy` — DONE (fixture-driven; CLR-012 + CLR-241 seeded in `data/ato_source_fixtures.py`)
  - `draft_strategy` — DONE (Claude Sonnet via `app/modules/tax_strategies/llm.py`; two-section output `## Implementation` / `## Explanation`; researching|enriched → drafted)
  - `enrich_strategy` — DONE (second LLM pass; structured JSON parsed with safe defaults; drafted → enriched)
- **Admin + public routers** — 11 routes mounted under `/api/v1/admin/tax-strategies` and `/api/v1/tax-strategies`. Registered in `backend/app/main.py`.
- **State machine**: `TaxStrategyService._transition_status` is the single chokepoint for `TaxStrategy.status` mutations; all stage-trigger methods route through it. 17 allowed edges enumerated in `_ALLOWED_TRANSITIONS`.
- **Audit**: six event types emitted per spec — `tax_strategy.created|status_changed|approved|published|superseded|seed_executed`
- **Seed action**: `seed_from_csv` in `service.py` + `POST /api/v1/admin/tax-strategies/seed-from-csv`. Transactional validation, idempotent, category allowlist enforced. CSV currently contains only a header row.
- **Latency tracer**: `tax_planning.retrieve.ms` log line on every `_retrieve_tax_knowledge` call

### Tests — DONE (252 green)

- 95 new unit tests in `backend/tests/unit/modules/tax_strategies/` across env_gate, service transitions, chunker, citation verifier CLR, markup normaliser, seed validator, ATO source fixtures, router smoke, **LLM prompts + response parsers (new, 17 tests)**
- 4 new unit tests in `backend/tests/unit/modules/tax_planning/test_retrieval_latency_tracer.py`
- **Regression**: 153 existing `tax_planning` tests still green

### Not done

| Area | Tasks | Notes |
|---|---|---|
| Backend integration tests | T022, T023, T024 | Need Celery worker + Pinecone + DB fixtures wired into test harness |
| LLM pipeline — end-to-end smoke | (follow-up) | Unit-tested parsers. Manual smoke against a live ANTHROPIC_API_KEY still pending — exercise CLR-012 research → draft → enrich via admin API and eyeball the drafted row |
| Frontend — chip layer | T038–T041 | StrategyChip, StrategyDetailSheet, useStrategyHydration, markdown tokenizer |
| Frontend — admin shell | T042–T045 | Add Strategies tab, list, detail Sheet with action bar, TanStack Query hooks |
| Frontend — US2 | T047, T048, T050 | CitationBadge extension, message-level count, graceful degradation guard |
| Frontend — US3 | T051–T056 | Filters, kanban pipeline, version history, authoring jobs log |
| Frontend — US4 | T062 | Seed button with confirmation dialog |
| Content | T059 | Populate the 415-row `strategy_seed.csv` from external reference material |
| Polish | T064a, T066 | Perf benchmark (needs 415 rows seeded), quickstart validation run |
| Close | TFINAL-* | PR, review, merge, ROADMAP update |

---

## Key decisions made during implementation (non-obvious)

These aren't in the spec; they're load-bearing choices I made while coding. Future-you should preserve them unless there's a good reason to revisit.

### 1. ContentChunk.source_id is NOT NULL → singleton KnowledgeSource

`content_chunks.source_id` is NOT NULL in the existing schema. Strategy chunks don't come from a scraped knowledge source. **Decision**: the publish task does a get-or-create for a singleton `KnowledgeSource` with `name="tax_strategies_internal"`, `source_type="tax_strategy"`, `base_url="clairo://tax_strategies"`. All strategy ContentChunk rows point at this singleton. Avoids a schema change.

Location: `backend/app/tasks/tax_strategy_authoring.py::_ensure_strategy_source`

### 2. Pinecone payload omits None-valued numeric bands

Pinecone rejects `None` metadata values. **Decision**: the publish task only includes `income_band_min/max`, `turnover_band_min/max`, `age_min/max` in the metadata payload when they're non-None. Retrieval-side filter uses `$or` + `$exists` to handle strategies with no bound.

Location: `backend/app/tasks/tax_strategy_authoring.py::_execute_publish` (the loop with `for col, value in ...`)

### 3. Two-pass retrieval is implemented but NOT YET wired into tax_planning

`strategy_hits.py` has `dedupe_and_rerank_strategies` with the full FR-018/FR-019 contract (dedupe by parent, batch fetch, SQL-side supersession filter, rerank on full parent content). But `_retrieve_tax_knowledge` in `tax_planning/service.py` does a simpler inline version (dedupe by `tax_strategy_id`, batch fetch via `TaxStrategyRepository.get_live_versions`, no second rerank — relies on chunk-level rerank from `search_knowledge`). The cross-encoder rerank-on-full-parent is still pending.

**Why the inline version**: by the time the results reach `_retrieve_tax_knowledge`, they're already reranked dicts from `KnowledgeService.search_knowledge`, not raw ScoredChunks. Threading raw chunks out would require a new method on `KnowledgeService` or bypassing its pipeline. I took the pragmatic shortcut.

**To fix properly**: either (a) add `KnowledgeService.search_knowledge_raw()` that returns ScoredChunks, or (b) move the tax-strategies-aware retrieval entirely into a new `TaxStrategyRetrievalService` that composes hybrid_search + strategy_hits directly. (b) is cleaner.

### 4. Markup normaliser runs BEFORE verifier

The order matters: near-miss forms like `CLR-241` are rewritten to `[CLR-241: Change PSI to PSB]` by the normaliser, THEN the verifier runs and classifies them. If the order were reversed, verified chips would drop to unverified just because of prompt drift. Both call sites (non-streaming chat + streaming `done` event) call the normaliser before `_build_citation_verification`.

### 5. Stage-trigger preconditions live separate from state machine

`_validate_stage_precondition` in the service maps stage name → allowed current statuses, but it's NOT the same as the `_ALLOWED_TRANSITIONS` set. Reason: triggering a stage is a "pre-condition check" (can I kick off this task?), distinct from the status transition itself (which happens asynchronously in the Celery task). Both use `InvalidStatusTransitionError` so the router maps consistently to 409.

### 6. Reviewer identity capture uses Clerk user ID + display name snapshot

`TaxStrategy.reviewer_clerk_user_id` is the live link to Clerk. `reviewer_display_name` is a snapshot (email or sub) captured at approval time. Both populated only on the `in_review → approved` transition (not earlier). Survives Clerk user deletion while keeping the audit row readable.

### 7. Seed validation aborts the whole run on any error

Transactional all-or-nothing. Partial inserts on a 415-row seed would be a nightmare to clean up. Error list is returned in `SeedValidationError.errors` so the frontend (T062) can render them as a list.

### 8. Near-miss citation patterns do NOT match canonical form

The normaliser's regex patterns explicitly exclude `[CLR-XXX: Non-empty name]`. Test `test_canonical_form_is_preserved_verbatim` guards this. If you're adding new patterns to the normaliser, run that test first.

---

## Gotchas discovered during implementation

- **Pinecone `isinstance(None, int)` rejection** → numeric-band handling above.
- **CSV DictReader with missing header columns**: `set(fieldnames) < expected` is strict subset, not "is superset". Fixed to `expected.issubset(present)` which gives the correct "header missing required columns" behavior.
- **Empty-string env var parsing**: Pydantic `bool` rejects empty string as "not a valid boolean". The env-gate test originally included `""` as a false-like value; removed. If the env var is explicitly set to empty, the app fails to start — caller should just unset.
- **Alembic migration must use `server_default=sa.text("gen_random_uuid()")`** for UUID primary keys or inserts without explicit id fail. (pgcrypto / postgres 16 default.)
- **`get_settings()` is `@lru_cache`d** → env-gate tests must `get_settings.cache_clear()` between monkeypatches. See `test_env_gate.py` autouse fixture.
- **SQLAlchemy `ForeignKey` declared in the model is redundant when the FK is created in the migration** — ruff flagged it as unused import. The migration does the real schema work.
- **Knowledge module public `router` path is `/api/v1/admin/knowledge` and public is `/api/v1/knowledge`** — mirrored this pattern for tax_strategies: `/api/v1/admin/tax-strategies` and `/api/v1/tax-strategies`.

---

## Suggested next session: three options

### Option A — Frontend (biggest user-visible impact)

Prerequisites: run `npm run dev` in `frontend/`; optionally start the backend too for real API testing. If super_admin testing is blocked, stub with `process.env.NEXT_PUBLIC_TEST_USER_ROLE`.

Order:
1. T038–T041 — StrategyChip + Sheet + useStrategyHydration + markdown tokenizer. These are the user-facing payoff.
2. T042–T045 — admin Strategies tab + detail Sheet with action bar + TanStack Query hooks.
3. T047, T048, T050 — message-level CitationBadge extension + graceful degradation.

### Option B — LLM pipeline (T028 draft + enrich)

Prerequisites: `ANTHROPIC_API_KEY` in `.env.local`; a way to exercise the Celery task locally. Look at how `tax_planning/agent.py` does Anthropic calls — mimic that pattern.

1. Write `draft_strategy` with the prompt from architecture §10.3. Use Claude Sonnet (`claude-sonnet-4-6`). Parse the response into `implementation_text` + `explanation_text`. Transition researching → drafted.
2. Write `enrich_strategy` second LLM pass. Extract structured eligibility into the existing columns. Default to NULL on low-confidence per architecture §16 mitigation.
3. End-to-end manual smoke: seed CLR-012, click Research → Draft → Enrich through the admin API with `curl`, inspect the row. (Approve + publish only works in prod due to the env gate.)

### Option C — Integration tests (T022, T023, T024)

Prerequisites: understand the existing `tests/integration/` harness setup — how Celery is mocked or pointed at a test broker, how Pinecone is mocked.

1. T022 — publish roundtrip against a 3-strategy fixture, asserting ContentChunk + BM25 + vector counts.
2. T023 — multi-namespace retrieval round trip.
3. T024 — admin API smoke against a running TestClient.

Heavier infra lift than A or B but gives real end-to-end confidence.

---

## Files to revisit when resuming

| File | Why |
|---|---|
| `specs/060-tax-strategies-kb/tasks.md` | Task checklist; shows `[X]` / `[ ]` per task |
| `specs/060-tax-strategies-kb/quickstart.md` | End-to-end walkthrough (some stages still stubbed) |
| `backend/app/tasks/tax_strategy_authoring.py` | `draft_strategy` + `enrich_strategy` are the NotImplementedError lines to fill |
| `backend/app/modules/tax_strategies/data/ato_source_fixtures.py` | Add entries for more slice strategies if Phase 1 demo covers >CLR-012/CLR-241 |
| `frontend/src/app/(protected)/admin/knowledge/page.tsx` | Add Strategies tab here (T042) |
| `frontend/src/components/tax-planning/` | New StrategyChip + hydration hook land here (T038–T041) |

---

## Unfinished artifacts on disk

These exist in the working tree but aren't in any commit (pre-existing, unrelated to this feature):

- `frontend/public/tax-planning-wireframes.html` — leave alone
- `specs/briefs/2026-04-18-llm-output-hardening.md` — leave alone

Don't stage them when committing 060 work.

---

## Quick facts

- **Test count**: 252 unit tests green as of the final commit.
- **Migration id**: `060_tax_strategies_phase1`, revises `059_1_as_at_date`.
- **Env flag name**: `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default `false`).
- **Pinecone namespace**: `tax_strategies` (shared — no env suffix).
- **Vector ID scheme**: `tax_strategy:{strategy_id}:{section}:v{version}`.
- **Canonical citation markup**: `[CLR-XXX: Name]`.
- **Name-drift threshold**: normalised Levenshtein ≥ 0.30.
- **Singleton KnowledgeSource name**: `tax_strategies_internal`.
