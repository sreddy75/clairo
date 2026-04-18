---
description: "Task list for 060-tax-strategies-kb Phase 1 implementation"
---

# Tasks: Tax Strategies Knowledge Base — Phase 1 Infrastructure

**Input**: Design documents from `/specs/060-tax-strategies-kb/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/, quickstart.md

**Tests**: Included. Constitution §V requires 80%+ unit coverage on services and 100% integration coverage on endpoints; §19.1 of the architecture doc enumerates ship-blocking CI tests.

**Organization**: Grouped by user story (US1, US2, US3, US4) per spec priorities.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (US1/US2/US3/US4)
- All paths are absolute or repo-relative from `/Users/suren/KR8IT/projects/Personal/clairo/`

## Path Conventions

- Backend module: `backend/app/modules/tax_strategies/`
- Backend tests: `backend/tests/unit/modules/tax_strategies/` and `backend/tests/integration/`
- Frontend admin: `frontend/src/app/(protected)/admin/knowledge/`
- Frontend chat components: `frontend/src/components/tax-planning/`

---

## Phase 0: Git Setup

- [ ] T000 Confirm feature branch `060-tax-strategies-kb` is checked out
  - Run: `git rev-parse --abbrev-ref HEAD` — expect `060-tax-strategies-kb`
  - If not: `git checkout 060-tax-strategies-kb`
  - _Branch already exists per recent commit `7735298 docs(060): spec tax strategies KB + supporting briefs and skills`_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Scaffold the new module and shared config changes that every subsequent task depends on.

- [X] T001 Create module skeleton at `backend/app/modules/tax_strategies/` with empty files: `__init__.py`, `models.py`, `schemas.py`, `repository.py`, `service.py`, `router.py`, `exceptions.py`, `audit_events.py`, `env_gate.py`, and subdirectory `data/` (per plan.md §Project Structure)
- [X] T002 [P] Register the new Celery queue `tax_strategies` in `backend/app/tasks/celery_app.py` (concurrency 2 dev / 4 prod; routes for `tax_strategies.research`, `tax_strategies.draft`, `tax_strategies.enrich`, `tax_strategies.publish`) per research.md R7
- [X] T003 [P] Add env var `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default `"false"`) to `backend/app/config.py` Pydantic settings; document in `.env.example`
- [X] T004 [P] Create empty Celery task stubs in `backend/app/tasks/tax_strategy_authoring.py` — four `@celery_app.task` functions named `research_strategy`, `draft_strategy`, `enrich_strategy`, `publish_strategy`, each routed to queue `tax_strategies`, bodies `raise NotImplementedError` (to be filled during US1)
- [X] T005 Create the seed CSV skeleton at `backend/app/modules/tax_strategies/data/strategy_seed.csv` with the header row only: `strategy_id,name,categories,source_ref` (rows added in US4)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Schema, models, repository, and retrieval-layer plumbing that every user story depends on.

**⚠️ CRITICAL**: No user story work can begin until this phase is complete.

### Schema + models

- [X] T006 Create Alembic migration `backend/alembic/versions/2026xxxx_tax_strategies_phase1.py` implementing data-model.md §1, §2, §3 — new tables `tax_strategies`, `tax_strategy_authoring_jobs`; three nullable columns on `content_chunks` (`tax_strategy_id`, `chunk_section`, `context_header`); indexes per data-model §1.1, §2.1
- [X] T007 Implement `TaxStrategy` + `TaxStrategyAuthoringJob` SQLAlchemy models in `backend/app/modules/tax_strategies/models.py` (fields, types, defaults, indexes per data-model §1, §2)
- [X] T008 Extend `ContentChunk` in `backend/app/modules/knowledge/models.py` — add nullable `tax_strategy_id` (FK to `tax_strategies.id`, `ON DELETE CASCADE`), `chunk_section` (String 32), `context_header` (String 300) per data-model §3

### Repository + service scaffolding

- [X] T009 [P] Implement `TaxStrategyRepository` in `backend/app/modules/tax_strategies/repository.py` with: `create`, `get_by_strategy_id`, `get_live_version`, `list_with_filters`, `list_versions`, `upsert_status`, `set_reviewer_snapshot`, `count_by_status` — all methods tenant-id aware, using `flush()` not `commit()` per constitution §III
- [X] T010 [P] Define domain exceptions in `backend/app/modules/tax_strategies/exceptions.py`: `StrategyNotFoundError`, `InvalidStatusTransitionError`, `VectorWriteDisabledError`, `DuplicateStrategyIdError`, `InvalidCategoryError`, `SeedValidationError`
- [X] T011 [P] Define the 6 audit event types in `backend/app/modules/tax_strategies/audit_events.py` per spec §Audit Events table (`tax_strategy.created`, `.status_changed`, `.approved`, `.published`, `.superseded`, `.seed_executed`)
- [X] T012 [P] Implement env gate helper in `backend/app/modules/tax_strategies/env_gate.py` — `def vector_writes_enabled() -> bool` reading `settings.TAX_STRATEGIES_VECTOR_WRITE_ENABLED`; unit test in `backend/tests/unit/modules/tax_strategies/test_env_gate.py` (monkeypatches the setting)

### Pinecone + retrieval plumbing

- [X] T013 Add `"tax_strategies"` entry to `NAMESPACES` dict in `backend/app/modules/knowledge/collections.py` (shared=True, filterable_fields per data-model §4); extend the `POST /admin/knowledge/initialize` endpoint path to create the namespace on first run (no change needed if the endpoint iterates `NAMESPACES` — verify); add integration test asserting `CollectionManager.get_all_stats()` returns the new namespace after init (FR-026)
- [X] T014 Extend `KnowledgeSearchRequest` in `backend/app/modules/knowledge/schemas.py` with `namespaces: list[str] | None = None` (default None preserves existing behaviour); extend `KnowledgeSearchFilters` with `income_band`, `turnover_band`, `age`, `industry_codes`, `tenant_id` per `contracts/knowledge-search-extensions.md`
- [X] T015 Extend `KnowledgeSearchResultSchema` in the same file with nullable fields `tax_strategy_id`, `strategy_name`, `categories`, `chunk_section` (all None for non-strategy results) per `contracts/knowledge-search-extensions.md` §3
- [X] T016 Pass `namespaces` through `KnowledgeService.search_knowledge` in `backend/app/modules/knowledge/service.py` to `HybridSearchEngine.hybrid_search(namespaces=...)`; default resolves to `["compliance_knowledge"]` when None
- [X] T017 Implement structured-eligibility pre-filter + fallback-to-unfiltered behaviour in `backend/app/modules/knowledge/retrieval/hybrid_search.py` per research.md R5 + contracts §2.1; log `retrieval.fallback.unfiltered` at INFO when triggered

### Central status-transition chokepoint

- [X] T018 Implement `TaxStrategyService._transition_status(old, new, strategy, actor, reviewer_snapshot=None)` in `backend/app/modules/tax_strategies/service.py` per data-model §1.2 — validates state-machine edges, emits audit events (`tax_strategy.status_changed`; also `.approved` on `in_review→approved`; also `.published` on `approved→published`)

### Two-pass retrieval (FR-018 / FR-019)

- [X] T018a Implement two-pass retrieval in `backend/app/modules/knowledge/retrieval/hybrid_search.py` (or a new `retrieval/strategy_hits.py`) — after hybrid chunk search returns candidates for namespace `tax_strategies`, dedupe by `tax_strategy_id` keeping max-scored chunk, batch-fetch parent `TaxStrategy` rows via `TaxStrategyRepository.get_live_version(strategy_ids)`, filter out rows whose `status IN ('superseded','archived')` (belt-and-braces SQL-side filter per research §R11), then cross-encoder rerank against **full parent content** (implementation_text + explanation_text concatenated) — architecture §9.4 / FR-018 / FR-019. Integration test covering a stale-vector case (vector exists in Pinecone but parent row has `status='superseded'`) asserting the strategy is excluded from results.

**Checkpoint**: Schema migrated, namespace registered, retrieval layer accepts new fields, two-pass dedupe+rerank implemented. No behaviour change for existing callers. US1–US4 can begin.

---

## Phase 3: User Story 1 — One strategy end-to-end (Priority: P1) 🎯 MVP

**Goal**: Super-admin advances one stub through research → draft → enrich → submit → approve → publish; retrieval + citation chip work end-to-end per quickstart.md.

**Independent Test**: Run quickstart §2–§3 against a single fixture strategy (`CLR-012`). Response in tax planning chat contains a green `[CLR-012: Concessional super contributions]` chip; clicking it opens the detail Sheet.

### Tests for User Story 1 (write-first where feasible)

- [X] T019 [P] [US1] Unit test in `backend/tests/unit/modules/tax_strategies/test_strategy_chunker.py` — asserts exactly 2 chunks per strategy (implementation + explanation), context header conforms to `[CLR-XXX: Name — Category: Y]`, body ends with `Keywords:` line, explanation splits at paragraph boundary when > 500 tokens (quickstart §4 / arch §19.1)
- [X] T020 [P] [US1] Unit test in `backend/tests/unit/modules/tax_strategies/test_citation_verifier_clr.py` — `extract_strategy_citations()` parses `[CLR-241: Change PSI to PSB]` across single-line, multi-line, with and without whitespace variations; rejects malformed markers (arch §19.1)
- [X] T021 [P] [US1] Unit test in `backend/tests/unit/modules/tax_strategies/test_service_lifecycle.py` — `_transition_status` accepts legal edges and rejects illegal ones (`stub → published` raises `InvalidStatusTransitionError`); reviewer snapshot captured on `in_review → approved`; audit events emitted
- [ ] T022 [US1] Integration test in `backend/tests/integration/test_publish_roundtrip.py` — 3-strategy fixture; `publish_strategy` produces exactly 2 ContentChunk rows + 2 BM25 rows + 2 Pinecone vectors per strategy; audit `tax_strategy.published` emitted with correct `chunk_count`; `strategy.status == 'published'` (quickstart §4 smoke test)
- [ ] T023 [US1] Integration test in `backend/tests/integration/test_retrieval_multi_namespace.py` — `KnowledgeSearchRequest(namespaces=["compliance_knowledge","tax_strategies"])` returns hits from both; defaults to current behaviour when `namespaces=None`; `content_type=="tax_strategy"` populates new result fields
- [ ] T024 [US1] Integration test in `backend/tests/integration/test_api_tax_strategies.py` — admin endpoints list / detail / research / draft / enrich / submit / approve / reject respond with expected statuses and produce expected side-effects (Celery task queued, status transition, audit row)
- [ ] T025 [P] [US1] Frontend test in `frontend/src/components/tax-planning/__tests__/StrategyChip.test.tsx` — renders green/amber/red per verification state prop; click opens Sheet; chip text matches the markup

### Implementation for User Story 1

#### Backend — chunker and publish pipeline

- [X] T026 [US1] Implement `StrategyChunker(BaseStructuredChunker)` in `backend/app/modules/knowledge/chunkers/strategy.py` per architecture §7 — two-chunk output (implementation + explanation), context header prefix, keyword tail, paragraph-boundary split when > 500 tokens
- [X] T027 [US1] Implement `publish_strategy` Celery task in `backend/app/tasks/tax_strategy_authoring.py` — calls `env_gate.vector_writes_enabled()`; on false, marks job failed with `vector_write_disabled_in_this_environment` and leaves strategy in `approved`; on true: chunk → embed via `VoyageService` → upsert Pinecone with deterministic vector IDs (`tax_strategy:{strategy_id}:{section}:v{version}`) → write `ContentChunk` + `BM25IndexEntry` rows → transition status to `published` via `_transition_status` (plan §Structure Decision, data-model §4.2)
- [ ] T028 [US1] Implement `research_strategy`, `draft_strategy`, `enrich_strategy` Celery tasks in the same file. Phase 1 shipping behaviour:
  - **research**: loads a pre-populated list of ATO source URLs from a per-strategy fixture map at `backend/app/modules/tax_strategies/data/ato_source_fixtures.py` (Phase 1 supplies entries for CLR-012 and 2–3 other slice strategies; Phase 2 replaces this with real ATO scraping). Writes `ato_sources` and transitions status.
  - **draft**: real Anthropic SDK call (Claude Sonnet) using the prompt at architecture §10.3. Reads the fixture-loaded `ato_sources`, emits `implementation_text` + `explanation_text`, writes via `_transition_status`. This is the demo-worthy path per quickstart §2b.
  - **enrich**: second real LLM pass extracting structured eligibility metadata (`entity_types`, `income_band_*`, `keywords`, etc.). Defaults to NULL/empty when the LLM returns low-confidence / ambiguous answers per architecture §16 mitigations.
- [X] T029 [US1] Implement `TaxStrategyService` stage-trigger methods in `backend/app/modules/tax_strategies/service.py`: `trigger_stage` (for research/draft/enrich/publish Celery dispatch), `submit_for_review`, `approve` (approved + queues publish task), `reject` — each validates current status, creates `TaxStrategyAuthoringJob` row, queues the Celery task or performs synchronous transition. (supersede defers to T056/follow-up.)

#### Backend — citation verifier

- [X] T030 [US1] Extend `CitationVerifier` in `backend/app/modules/knowledge/retrieval/citation_verifier.py` with `CLR_PATTERN`, `extract_strategy_citations()`, and `verify_strategy_citations(text, retrieved_set)` — returns list with status `verified | partially_verified | unverified` per FR-020; name drift uses normalized Levenshtein ≥ 0.30 on lower-cased whitespace-collapsed strings
- [ ] T031 [US1] Extend `_build_citation_verification()` in `backend/app/modules/tax_planning/service.py` to include `strategy_citations` array alongside section-ref + ruling-number arrays; overall status collapses per existing logic

#### Backend — tax planning retrieval wiring

- [ ] T032 [US1] Modify `TaxPlanningService._retrieve_tax_knowledge()` in `backend/app/modules/tax_planning/service.py` to pass `namespaces=["compliance_knowledge", "tax_strategies"]` and populate `KnowledgeSearchFilters.income_band/turnover_band/age/industry_codes/tenant_id` from the tax plan's client context (research §R8) — no other call sites touched
- [ ] T033 [US1] Wrap `content_type=="tax_strategy"` results in the `<strategy>` XML envelope in the tax planning LLM context assembly path (architecture §9.5 / contracts knowledge-search-extensions §4); update the tax planning system prompt in `backend/app/modules/tax_planning/prompts.py` with the `[CLR-XXX: Name]` citation instruction

#### Backend — admin + public API

- [X] T034 [US1] Implement admin router in `backend/app/modules/tax_strategies/router.py` per `contracts/admin-tax-strategies.openapi.yaml` — endpoints `GET /tax-strategies`, `GET /tax-strategies/{strategy_id}`, `POST .../research|draft|enrich|submit|approve|reject|supersede`, `GET /tax-strategies/pipeline-stats`. Include Clerk `super_admin` role gate (reuse existing admin dependency)
- [X] T035 [US1] Implement public hydration router (same file or separate; mounted at `/api/v1/tax-strategies/.../public`) per `contracts/public-tax-strategies.openapi.yaml` — strips `source_ref` from the response (FR-008); only returns `status=='published'` + non-superseded + tenant-visible rows
- [X] T036 [US1] Register the tax_strategies router(s) in `backend/app/main.py` (or `backend/app/api/v1/__init__.py` following existing registration pattern)
- [X] T037 [US1] Implement Pydantic request/response schemas in `backend/app/modules/tax_strategies/schemas.py` matching `contracts/admin-tax-strategies.openapi.yaml` and `contracts/public-tax-strategies.openapi.yaml`

#### Frontend — chip + hydration

- [ ] T038 [P] [US1] Implement `StrategyChip` component in `frontend/src/components/tax-planning/StrategyChip.tsx` — green/amber/red Badge variants, renders `[CLR-XXX: Name]`, onClick opens `StrategyDetailSheet`
- [ ] T039 [P] [US1] Implement `StrategyDetailSheet` in `frontend/src/components/tax-planning/StrategyDetailSheet.tsx` — uses shadcn `Sheet`; shows implementation + explanation + ATO sources + case refs; hydrates via `useStrategyHydration`
- [ ] T040 [P] [US1] Implement `useStrategyHydration` hook in `frontend/src/components/tax-planning/useStrategyHydration.ts` — takes `strategy_ids: string[]`, returns TanStack Query result hydrating `GET /tax-strategies/public?ids=...`; caches by id
- [ ] T041 [US1] In the chat message markdown renderer (identify in `frontend/src/components/tax-planning/` — likely `ScenarioChat.tsx` or a message component), add a tokenizer that converts `[CLR-XXX: Name]` substrings into `<StrategyChip/>` React nodes before markdown rendering (architecture §11.4)

#### Frontend — admin shell

- [ ] T042 [US1] Add `"Strategies"` to the `TABS` array in `frontend/src/app/(protected)/admin/knowledge/page.tsx` (icon: `ListChecks` from lucide-react); mount `StrategiesTab` component
- [ ] T043 [US1] Implement `StrategiesTab` in `frontend/src/app/(protected)/admin/knowledge/components/strategies-tab.tsx` — list table (columns: strategy_id, name, categories, status, last_reviewed, reviewer, version); row click opens detail Sheet; minimal filters (status only in US1 — full filter set in US3)
- [ ] T044 [US1] Implement `StrategyDetailSheet` admin variant in `frontend/src/app/(protected)/admin/knowledge/components/strategy-detail-sheet.tsx` — read-only field rendering + action bar with six buttons (Research / Draft / Enrich / Submit for review / Approve & publish / Reject). Each button disabled unless current status permits (per research.md R9)
- [ ] T045 [US1] Implement `useTaxStrategies` hooks in `frontend/src/app/(protected)/admin/knowledge/hooks/use-tax-strategies.ts` — TanStack Query: `useStrategyList`, `useStrategyDetail`, `useTriggerStage` mutations for each action; optimistic updates with rollback on error

**Checkpoint**: CLR-012 can be driven end-to-end per quickstart §2–§3. Green StrategyChip renders in chat. Quickstart §2–§3 passes manually. This is the MVP increment.

---

## Phase 4: User Story 2 — Citation trust visible to accountants (Priority: P1)

**Goal**: The green / amber / red three-state rendering and message-level citation summary work for every strategy citation path.

**Independent Test**: Feed a tax-planning chat response containing one verified `[CLR-012]`, one name-drift `[CLR-012: Something else]`, and one hallucinated `[CLR-999: Fake]`. Expect green + amber + red chips respectively; message-level `CitationBadge` shows mixed verification.

### Tests for User Story 2

- [ ] T046 [P] [US2] Unit test in `backend/tests/unit/modules/tax_strategies/test_citation_verifier_states.py` — three table-driven cases (exact match → `verified`; identifier match + name drift ≥ 0.30 → `partially_verified`; no match → `unverified`); confirms spec SC-007 paths
- [ ] T047 [P] [US2] Frontend test in `frontend/src/components/tax-planning/__tests__/CitationBadge.test.tsx` — message-level badge renders combined verification state + strategy-citation count alongside existing section-ref/ruling counts

### Implementation for User Story 2

- [ ] T048 [US2] Extend `CitationBadge` in `frontend/src/components/tax-planning/CitationBadge.tsx` — include count of strategy citations (verified / partial / unverified) in the summary line; overall badge colour rolls up to the worst component state
- [ ] T049 [US2] Ensure the verification summary from `_build_citation_verification()` (T031) serialises `strategy_citations` array into the message payload persisted on `ChatMessage.citations`; add a migration note or repository update if the field shape needs extending (verify shape in `backend/app/modules/tax_planning/models.py` — `ChatMessage.citations` JSONB already holds arbitrary list, likely no schema change)
- [ ] T050 [US2] Add the graceful-degradation guard in the frontend chat renderer (T041 location) — when `StrategyChip` hydration fails (404 / network), still render the chip in red with title attribute `"Strategy not found"` and a muted icon; never break the message rendering (spec §Edge Cases: "hallucinated identifier ... must not break the response render")

**Checkpoint**: Three-color rendering demonstrable with controlled test fixtures. Spec SC-007 paths all visible.

---

## Phase 5: User Story 3 — Admin surfaces for strategy governance (Priority: P2)

**Goal**: Super-admin can filter the list, view the pipeline kanban, and inspect version/authoring-job history read-only.

**Independent Test**: Open the Strategies tab with 415 stub records seeded. Apply status filter "in_review" → only in-review rows. Open any detail → version history + authoring jobs render correctly. Open Pipeline sub-tab → counts render accurately.

### Tests for User Story 3

- [ ] T051 [P] [US3] Frontend test in `frontend/src/app/(protected)/admin/knowledge/components/__tests__/strategies-tab.test.tsx` — filters compose correctly (status + category + tenant); pagination links advance; list row click opens Sheet
- [ ] T052 [P] [US3] Integration test in `backend/tests/integration/test_pipeline_stats.py` — `GET /tax-strategies/pipeline-stats` returns accurate counts across all 9 statuses with mixed test data

### Implementation for User Story 3

- [ ] T053 [US3] Extend `StrategiesTab` (T043) with full filter set — category multi-select (8 options), tenant filter (`platform` / specific tenant UUID — Phase 1 shows only `platform`), search box (matches name + strategy_id)
- [ ] T054 [US3] Implement status-count header counters in `StrategiesTab` ("Published 97 / In review 12 / Drafted 31 / Stub 275") pulling from `GET /pipeline-stats`
- [ ] T055 [US3] Implement `StrategiesPipeline` kanban view in `frontend/src/app/(protected)/admin/knowledge/components/strategies-pipeline.tsx` — columns per status, card per strategy, in-review column visually highlighted per spec User Story 3 Acceptance Scenario 4; mount as a sub-tab inside Strategies (tab within tab, or a toggle in the top bar)
- [ ] T056 [US3] Extend `StrategyDetailSheet` (T044) — version history list (shows each row with version number, status, timestamp; click opens that version read-only), authoring-jobs log (table of `TaxStrategyAuthoringJob` rows with stage/status/timestamps/error)

**Checkpoint**: Admin list + pipeline kanban + detail view history all functional. Spec SC-008 (415-row list under 500ms) validated.

---

## Phase 6: User Story 4 — Seeding the catalogue (Priority: P2)

**Goal**: A super-admin runs a one-time seed action that creates 415 stub records from the committed CSV. Re-running is idempotent.

**Independent Test**: On an empty catalogue, click "Seed from CSV" (or `POST /seed-from-csv`). Expect 415 created, 0 skipped. Re-run: 0 created, 415 skipped. Filter by each of the 8 categories; counts match the blueprint taxonomy.

### Tests for User Story 4

- [ ] T057 [P] [US4] Unit test in `backend/tests/unit/modules/tax_strategies/test_seed_idempotent.py` — first run creates N rows; second run with same CSV creates 0 rows and skips N; `strategy_id` collision is reported as skipped not errored; malformed category fails the whole run per research §R6
- [ ] T058 [P] [US4] Integration test in `backend/tests/integration/test_seed_from_csv.py` — `POST /seed-from-csv` end-to-end; asserts `tax_strategy.seed_executed` audit row + per-row `tax_strategy.created` audit rows + 415 DB rows after first successful run

### Implementation for User Story 4

- [ ] T059 [US4] Populate `backend/app/modules/tax_strategies/data/strategy_seed.csv` with 415 rows — derived once from the external reference material at `/Users/suren/KR8IT/projects/Personal/Clairo docs/Tax Fitness Strategy/` (not consumed at seed time per spec clarification). Each row: `CLR-###, Name, Category1|Category2, STP-###`. IDs sequential `CLR-001`..`CLR-415`. _Commit this file with the PR so code review can inspect the full catalogue._
- [ ] T060 [US4] Implement `seed_from_csv(csv_path, triggered_by) -> SeedSummary` in `backend/app/modules/tax_strategies/service.py` per data-model §5.1 — transactional, idempotent, validates categories against the fixed taxonomy, refuses the whole run on any invalid row
- [ ] T061 [US4] Add `POST /tax-strategies/seed-from-csv` endpoint to the admin router (T034) — super-admin only; returns `SeedSummary`
- [ ] T062 [US4] Add "Seed from CSV" action button to `StrategiesTab` top bar (T043/T053) — confirmation dialog before execution; shows result toast with created/skipped counts

**Checkpoint**: 415 stubs seeded; re-run idempotent. Spec SC-002 validated.

---

## Phase 7: Polish & Cross-Cutting Concerns

- [ ] T063 [P] Add structured logging tracer `tax_planning.retrieve.ms` per research §R4 — wraps the `_retrieve_tax_knowledge` call path; logs p50/p95 via existing `app.core.logging`
- [ ] T064 [P] Confirm `SC-004` — run the existing test suites for `client_chat`, `knowledge_chat`, `tax_planning`, `insights` unchanged; no regression when `namespaces=None`. Additionally: integration test that a non-prod environment (write flag unset) can successfully read from the shared `tax_strategies` namespace after prod-side publish (FR-029).
- [ ] T064a [P] Performance check (SC-008) — run `GET /api/v1/admin/tax-strategies?page_size=415` locally with all 415 stubs seeded, assert p95 response time ≤ 500ms over 10 runs; record numbers in quickstart validation notes.
- [ ] T064b [P] Code-layer citation markup normaliser (constitution §VIII) — add a post-processor in the tax-planning response path that rewrites near-miss citation forms (`(CLR-###)`, `CLR-###` unbracketed, `[CLR-###]` with missing name) into canonical `[CLR-###: <name-from-retrieved-set>]` when a retrieved strategy's identifier matches; unmatched near-misses are left alone for the verifier to classify as unverified. Unit test covering 4 near-miss inputs plus 1 canonical input. Prevents prompt drift from degrading chip coverage.
- [ ] T065 [P] Update `specs/ROADMAP.md` — mark 060 as **In Progress** (current phase) and stub Phase 2 follow-up
- [ ] T066 Run `quickstart.md` validation end-to-end against local environment with CLR-012 fixture strategy; document any deviations
- [ ] T067 [P] Full validation pass: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass — `cd backend && uv run pytest` and `cd frontend && npm test`
- [ ] TFINAL-2 Run linting and type checking — `cd backend && uv run ruff check .` and `cd frontend && npm run lint && npx tsc --noEmit`
- [ ] TFINAL-3 Push branch and create PR — `git push -u origin 060-tax-strategies-kb` then `gh pr create --title "Spec 060: Tax Strategies Knowledge Base — Phase 1 Infrastructure" --body "<summary of US1–US4; note Phase 2 content authoring out of scope>"`
- [ ] TFINAL-4 Address review feedback; push additional commits
- [ ] TFINAL-5 Merge PR to main (squash)
- [ ] TFINAL-6 Update `specs/ROADMAP.md` — mark 060 as COMPLETE; flag Phase 2 (content authoring with Unni) as next

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git)** → **Phase 1 (Setup)** → **Phase 2 (Foundational)** → **Phases 3–6 (US1–US4)** → **Phase 7 (Polish)** → **Phase FINAL (PR)**
- Phase 2 blocks all user story work.
- Within Phase 2: T006 (migration) blocks T007 (models); T008 (ContentChunk extension) can proceed in parallel with T007. T009–T012 (repository/exceptions/audit/env-gate) are [P] after T007 + T008 land. T013–T017 (retrieval plumbing) are [P] with T009–T012. T018 (status transitions) depends on T007 + T011.

### User Story Dependencies

- **US1 (MVP)** — depends only on Phase 2. Builds every capability needed for the end-to-end proof.
- **US2 (citation trust)** — shares code with US1 (verifier, StrategyChip). Separate acceptance criterion (three-color coverage). Can overlap with US1 tasks T030 / T038.
- **US3 (admin governance)** — depends on US1 (list endpoint, detail Sheet). Adds filters + kanban + history.
- **US4 (seeding)** — independent of US1 except via the shared admin router (T034). Can proceed in parallel with US1 once T007, T010, T011, T034 are complete.

### Within Each User Story

- Tests for US1 (T019–T025) MUST be written and observed RED (failing) **before** the paired implementation merges. Constitution §V Test-First Development is non-negotiable — "alongside" is insufficient; red-then-green is the rule.
- Backend chunker (T026) blocks publish (T027); publish (T027) blocks the integration test (T022).
- Router (T034) blocks frontend hooks (T045); hooks block Sheet (T044) and Tab (T043).
- `[CLR-XXX]` extractor (T030) blocks the tax-planning verifier extension (T031); T031 blocks the chat-message frontend integration (T041).

### Parallel Opportunities

- **Phase 1**: T002, T003, T004 all [P].
- **Phase 2**: After T007 + T008 merge, T009–T017 can all run in parallel as they touch different files.
- **Phase 3 (US1)**:
  - All unit/test tasks T019, T020, T021, T025 are [P].
  - Backend files: T026 (chunker), T030 (verifier), T037 (schemas) are different files → [P].
  - Frontend files: T038, T039, T040 are different files → [P].
- **Phases 3/4/5/6** can be split across developers once Phase 2 completes (constitution §XII parallel team strategy).

---

## Parallel Example: User Story 1 kick-off

```bash
# After Phase 2 completes, launch in parallel:
Task: "T019 Unit test for StrategyChunker"
Task: "T020 Unit test for CLR citation extractor"
Task: "T021 Unit test for status transitions"
Task: "T026 Implement StrategyChunker class"
Task: "T030 Extend CitationVerifier with CLR pattern"
Task: "T037 Pydantic schemas for admin + public endpoints"
Task: "T038 Frontend StrategyChip component"
Task: "T039 Frontend StrategyDetailSheet component"
Task: "T040 Frontend useStrategyHydration hook"
```

---

## Implementation Strategy

### MVP First (User Story 1)

1. Complete Phase 1 (Setup).
2. Complete Phase 2 (Foundational — schema, models, repo, retrieval plumbing). Blocking.
3. Complete Phase 3 (US1) — the one-strategy-end-to-end proof.
4. **STOP and VALIDATE**: run quickstart.md §2–§3 with CLR-012 fixture.
5. Decision point: deploy MVP to dev for Suren to click through, or continue to US2–US4.

### Incremental Delivery

1. Setup + Foundational → branch reviewable, migration reviewable.
2. US1 complete → CLR-012 cited end-to-end; demo-able.
3. US2 complete → three-color citation trust demo-able.
4. US3 complete → admin governance surfaces demo-able with filters + kanban.
5. US4 complete → 415 stubs seeded; pipeline ready for Phase 2 content authoring.

### Parallel Team Strategy

- After Phase 2 completes:
  - Dev A: US1 backend chain (T026 → T027 → T029 → T032 → T033 → T034)
  - Dev B: US1 frontend chain (T038 → T039 → T040 → T041 → T042 → T043 → T044 → T045)
  - Dev C: US3 + US4 (admin polish + seed) — depends on T034 / T043 being reachable but not complete

---

## Notes

- Tests are required per constitution §V. All test tasks must fail before the corresponding implementation merges.
- Every lifecycle transition runs through `_transition_status` (T018) — no other code path mutates `TaxStrategy.status`.
- `source_ref` must never appear in a public-hydration response. Router-level filter is the single enforcement point (T035).
- `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` is the sole arbiter of vector writes. Publish failures when the flag is false are intentional and visible in the admin pipeline dashboard.
- Phase 2 content authoring (real LLM drafting for 100 strategies; gold-set construction; recall/precision benchmarking) is **out of scope** for this tasks list — enumerated in the spec's Out of Scope and Assumptions sections.
