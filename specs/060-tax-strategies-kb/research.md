# Phase 0 Research — Tax Strategies KB (060)

Resolves the residual unknowns identified during `/speckit.plan`. Each section follows **Decision / Rationale / Alternatives considered**.

---

## R1. Environment gate mechanism for production-only vector writes

**Decision**: Dedicated env var `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default `"false"`). Parsed in `app/modules/tax_strategies/env_gate.py` as `def vector_writes_enabled() -> bool`. The publish Celery task calls it immediately before any Pinecone upsert; if false, the task sets the `TaxStrategyAuthoringJob` row to `failed` with a fixed error code `vector_write_disabled_in_this_environment`. The strategy remains in `approved` status per FR-011.

**Rationale**: Single-purpose flag; no coupling to `ENVIRONMENT=production` (which drifts over time — staging was once "production" of a parallel deployment). Easy to assert on in unit tests by flipping the var with `monkeypatch`. Fails loudly (job marked failed) rather than silently skipping, which makes env misconfiguration discoverable in the admin pipeline dashboard.

**Alternatives considered**:
- Infer from `ENVIRONMENT == "production"`: rejected — couples vector-write rule to environment naming, harder to audit.
- DB-backed feature flag: rejected — bootstrap problem (who seeds it?); adds a new persistent config surface.
- Allowlist in config file: rejected — YAML/TOML drift; one env var is simpler and tracked in deployment config already.

---

## R2. Reviewer identity source for FR-006

**Decision**: The approver's Clerk user ID (string, 120 chars) is captured from the request JWT via the existing admin auth dependency and stored in `TaxStrategy.reviewer_clerk_user_id`. A human-readable `reviewer_display_name` is additionally captured at approval time (snapshot, not FK) to survive Clerk account deletions.

**Rationale**: Clerk is the canonical super-admin identity provider (constitution §IX). Storing a snapshot display name lets the audit trail stay readable even if the Clerk user is later deleted or renamed; tying via Clerk ID keeps the link live. Avoids a circular dependency on a local `users` table that may lag Clerk.

**Alternatives considered**:
- FK to `practice_users`: rejected — tax strategies are platform-scoped, not per-tenant; `practice_users` is tenant-scoped.
- Clerk user ID only: rejected — loses the display name if the Clerk user is deleted; audit row becomes unreadable.
- Free-text reviewer name only: rejected — breaks FR-006 requirement for identifying the reviewer in audit and chain-of-custody.

---

## R3. BM25 index rebuild after publish

**Decision**: After `publish_strategy` writes the 2 `ContentChunk` rows and corresponding Pinecone vectors, it writes **2 matching `BM25IndexEntry` rows** in the same transaction as the ContentChunk inserts. The existing `HybridSearchEngine.hybrid_search` hydrates BM25 from `BM25IndexEntry` rows at query time (existing behaviour — verified by reading `retrieval/hybrid_search.py`), with an in-process LRU cache on the hydrated index. The cache key includes the namespace; publishing a new strategy invalidates the `tax_strategies` cache entry.

**Rationale**: Reuses the existing BM25 hydration pattern — no new index-rebuild job required. The LRU cache invalidation is a tiny cache-bust, not a background index rebuild. Phase 1's 415 strategies × 2 chunks = 830 rows fits comfortably in-memory (total BM25 footprint remains under 10 MB), so the rehydration cost is negligible even on cold cache.

**Alternatives considered**:
- On-demand index rebuild Celery task: rejected — unnecessary complexity for the corpus size; also introduces a window where the newly-published strategy is searchable semantically but not lexically.
- In-process incremental BM25 update: rejected — the `rank_bm25` library used doesn't support incremental updates cleanly; rebuild-from-rows is the supported path.

---

## R4. Retrieval latency budget and measurement

**Decision**: Target p95 ≤ 800ms end-to-end for tax planning chat with `namespaces=["compliance_knowledge", "tax_strategies"]` and structured eligibility filters populated. Budget allocation:
- 50 ms — query embedding (Voyage 3.5 lite, cached when repeat)
- 150 ms — Pinecone multi-namespace search (30 candidates per namespace)
- 50 ms — BM25 hybrid fusion + RRF
- 100 ms — dedupe-by-parent + parent row fetch (SQL batch select by `tax_strategy_id IN (...)`)
- 400 ms — cross-encoder rerank (top 30 → top 8)
- 50 ms — envelope construction + return

Measured via existing `logging.py` structured-logging tracer emitting `tax_planning.retrieve.ms` metric. Latency regression below threshold for two consecutive observed runs is an alerting condition in Phase 2 (out of scope here but instrumentation lands in Phase 1).

**Rationale**: Numbers align with the architecture §19.4 target and reflect the current hybrid pipeline's observed per-component costs. Instrumentation-in-Phase-1 lets Phase 2's gold-set work actually measure something.

**Alternatives considered**:
- Skip cross-encoder when corpus is small: rejected — consistency of retrieval shape across small and large corpora matters for test determinism.
- Parallelise embedding + BM25: rejected — negligible savings at these sizes; adds async-orchestration complexity.

---

## R5. Tenant filter construction in Pinecone query

**Decision**: Build the pinecone filter server-side in `KnowledgeService.search_knowledge` as:

```python
tenant_filter = {"tenant_id": {"$in": ["platform", request.tenant_id]}}
```

where `request.tenant_id` is derived from the FastAPI request context (middleware-set, per constitution §IV). For Phase 1 (no overlay strategies exist), this collapses to `"platform"`-only matches in practice but the union form is wired from day one so Phase 3 overlay ships without refactor.

**Rationale**: Matches architecture §14 verbatim. Sets the invariant early so Phase 3 is purely a content-layer change.

**Alternatives considered**:
- `tenant_id == "platform"` only in Phase 1: rejected — we'd have to touch every retrieval path again in Phase 3.
- Frontend-constructed filter: rejected — cross-tenant leakage risk; filter construction is a trust boundary that belongs in the server.

---

## R6. Seed CSV format and derivation

**Decision**: Single CSV file at `backend/app/modules/tax_strategies/data/strategy_seed.csv` with header `strategy_id,name,categories,source_ref`. Columns:

- `strategy_id` — `CLR-###` (zero-padded 3 digits; Phase 1 uses `CLR-001` through `CLR-415`).
- `name` — human-readable title, max 200 chars; matches FR-001 constraint.
- `categories` — pipe-delimited list of category keys from the fixed taxonomy of 8 (`Business`, `Recommendations`, `Employees`, `ATO_obligations`, `Rental_properties`, `Investors_retirees`, `Business_structures`, `SMSF`). Multi-tag per FR-003.
- `source_ref` — internal-only reference (e.g. `STP-241`); never surfaced (FR-008).

Seed action is driven by `tax_strategies.service.seed_from_csv()`. Idempotency enforced by `SELECT ... WHERE strategy_id IN (...)` pre-check; existing rows are skipped (not updated). All other fields (implementation/explanation text, eligibility metadata, status) are left at their defaults — the seed produces `stub` records only.

**Rationale**: CSV is trivial to review in PRs (line-based diffs), has no binary-parser dependency, and keeps the file self-describing. Pipe-delimited categories fit inside a single column without quoting gymnastics.

**Alternatives considered**:
- JSON fixture: rejected — verbose; diffs noisier; no practical benefit at this shape.
- YAML fixture: rejected — same tooling cost as JSON; indentation bugs are common.
- Parse xlsx at runtime from external path: rejected — external path non-portable across environments; format not under our control; binary diffs.

---

## R7. Celery queue provisioning

**Decision**: Add a new queue named `tax_strategies` to the Celery worker config. The four authoring tasks (`tax_strategies.research`, `tax_strategies.draft`, `tax_strategies.enrich`, `tax_strategies.publish`) are all routed to this queue. Worker concurrency for this queue is set to 2 in dev (sufficient for the fixture slice) and 4 in prod.

**Rationale**: Isolates the strategy-authoring workload from the existing `xero_writeback`, `bas`, and default queues so a slow LLM drafting call doesn't starve time-sensitive lodgement work. Mirrors the pattern used for `xero_writeback` (spec 049).

**Alternatives considered**:
- Reuse default queue: rejected — LLM calls in draft/enrich can run 10s+; blocks faster jobs.
- Separate queue per stage: rejected — premature; one queue handles Phase 1's throughput trivially.

---

## R8. Retrieval integration point in `tax_planning` module

**Decision**: Modify only `TaxPlanningService._retrieve_tax_knowledge()` (single method, ~80 lines). Changes:
1. Pass `namespaces=["compliance_knowledge", "tax_strategies"]` to the `KnowledgeSearchRequest`.
2. Populate new structured-eligibility fields on `KnowledgeSearchFilters` from the tax plan's client context (income, turnover, age, industry codes) where those are already present on the plan.
3. After receiving results, wrap any results with `content_type == "tax_strategy"` in the `<strategy>` XML envelope for the LLM; leave compliance results untouched.
4. Update the tax planning system prompt to describe the `[CLR-XXX: Name]` citation convention.

No other call sites touched. Existing callers of `KnowledgeService.search_knowledge` (client chat, knowledge chat, insight engine) are unaffected — the default `namespaces=None` preserves current behaviour (SC-004).

**Rationale**: Keeps the change surface minimal; isolates risk to the one tax-planning retrieval hook. The spec explicitly calls out this integration point (§Dependencies, §13 arch).

**Alternatives considered**:
- Add a new retrieval entry point `search_with_strategies`: rejected — duplicates the retrieval pipeline; two code paths to maintain.
- Opt-in namespace via a feature flag: rejected — the flag would immediately be turned on; deferring behind a flag adds a dead lever.

---

## R9. Action-button interactions in Phase 1 admin detail view

**Decision**: The strategy detail Sheet in Phase 1 renders fields **read-only** but exposes an action bar with six stage-trigger and transition buttons:
- **Research** (allowed if status in `{stub}`)
- **Draft** (allowed if status in `{researching, enriched}`)
- **Enrich** (allowed if status in `{drafted}`)
- **Submit for review** (allowed if status in `{enriched}`)
- **Approve & publish** (allowed if status in `{in_review}` — triggers `publish` task; reviewer capture happens here)
- **Reject** (allowed if status in `{in_review}` — returns to `drafted`)

Each button calls the corresponding `POST /admin/tax-strategies/{id}/{action}` endpoint; the table refreshes on success. Field editing (markdown editors, eligibility form controls) is deferred to Phase 2.

**Rationale**: Meets the Q4 clarification (action buttons in scope, field editing deferred). Keeps the Phase 1 UI surface small but complete enough to drive the one-strategy-end-to-end exit criterion.

**Alternatives considered**:
- Separate "admin actions" page: rejected — unnecessary surface, breaks the Sheet pattern.
- Only expose actions via CLI/API: rejected — violates the user-story test for super-admin admin interface.

---

## R10. Citation verifier extensions — parse precedence

**Decision**: Extend `CitationVerifier` with a single new `extract_strategy_citations(text) -> list[StrategyCitation]` method using regex `\[CLR-(\d{3,5}):\s*([^\]]+)\]`. Extraction runs independently of the existing `[Source: ...]` pattern — both run against the same response; results are combined into the `CitationVerificationSummary`. Strategy citations classify as `verified | partially_verified | unverified` per FR-020 (exact `strategy_id` match / Levenshtein ≥ 0.30 name drift / no match).

Matching uses the **retrieved-strategies set** passed to the LLM for that response, not a global lookup. This ensures a hallucinated `CLR-999` (or a real `CLR-241` that wasn't actually surfaced for this query) renders as unverified — consistent with the verifier's existing semantics for compliance citations.

**Rationale**: Mirrors the existing verifier's "was this actually in the retrieved context?" rule, which is the correct semantics for trust reporting.

**Alternatives considered**:
- Match against full `tax_strategies` table: rejected — a real identifier that wasn't retrieved for this query is still hallucinated behaviour; should flag red.
- Strip whitespace and match exact name: rejected — over-strict; the Levenshtein ≥ 0.30 threshold is what the spec pinned.

---

## R11. Superseded-filtering semantics

**Decision**: Retrieval filter always includes `{"is_superseded": {"$ne": True}}` on the Pinecone side (already present for `compliance_knowledge`) AND `status NOT IN ('superseded', 'archived')` on the SQL parent-fetch side. Double filter defends against the case where the vector metadata is stale relative to the parent row (e.g. a strategy was just superseded but the vector hasn't been re-upserted with `is_superseded=true` yet).

**Rationale**: Edge case in spec §Edge Cases ("Superseded strategies: a strategy whose replacement has published must not appear in retrieval results, even if its vector still exists in the shared store") demands this. Cheap belt-and-braces — SQL filter is free at parent-fetch time.

**Alternatives considered**:
- Pinecone filter only: rejected — relies on vector metadata being perfectly in sync.
- Background sync job: rejected — adds moving parts; simpler to double-filter.

---

## R12. Audit event emission points

**Decision**: Six audit events per spec §Audit Events table. Emission points:

| Event | Emitted by |
|---|---|
| `tax_strategy.created` | `seed_from_csv` (per row) + `POST /tax-strategies` (single-row create, if used) |
| `tax_strategy.status_changed` | `TaxStrategyService._transition_status` — central chokepoint called by all stage/action handlers |
| `tax_strategy.approved` | Emitted in addition to `status_changed` by the approve action specifically |
| `tax_strategy.published` | Emitted by `publish_strategy` Celery task on successful Pinecone upsert |
| `tax_strategy.superseded` | Emitted by `supersede_strategy` when creating the replacement row |
| `tax_strategy.seed_executed` | Emitted once by `seed_from_csv` summarising counts; independent of per-row `tax_strategy.created` events |

All events use the existing `app.core.audit.audit_event()` helper. Integration tests assert presence per §19.1.

**Rationale**: Centralising lifecycle transitions in `_transition_status` guarantees no path into a new status bypasses the audit row; the dedicated `approved` and `published` events carry the richer payload the spec table requires.

**Alternatives considered**:
- SQLAlchemy event listeners on status column: rejected — harder to attach rich payloads (reviewer identity, chunk count) at the ORM-event level.
- Event per endpoint: rejected — proliferates emission points, easier to miss one.

---

## Open items deferred to Phase 2

- **Gold-set construction** — Unni-labelled query→strategy set for recall@5 / precision benchmarking.
- **Retrieval quality tuning** — query-expansion prompt refinement, rerank top-k tuning.
- **Structured-eligibility enrichment accuracy review** — A/B vs unfiltered baseline.
- **Field editing UI** — markdown editors, eligibility form controls, diff view.

These are explicitly out of scope per the spec's Assumptions and the architecture doc's phased rollout.
