# Quickstart — Tax Strategies KB Phase 1 vertical slice

Proves the one-strategy-end-to-end path (SC-001): stub → researching → drafted → enriched → in_review → approved → published → cited in tax planning chat. Expected wall time ≤ 30 minutes after migrations apply.

Chose `CLR-012` (Concessional super contributions) as the vertical-slice candidate per architecture §18 — mid-complexity, high-frequency, clean ATO primary sources.

---

## 0. One-time setup (local dev)

```sh
# Backend
cd backend
uv run alembic upgrade head                     # applies 2026xxxx_tax_strategies_phase1

# Environment (local dev)
export TAX_STRATEGIES_VECTOR_WRITE_ENABLED=true  # local writes to a dev-only namespace override
export ENVIRONMENT=development

# Celery worker — new queue
cd ..
docker-compose up -d redis postgres pinecone-emulator
cd backend
uv run celery -A app.tasks.celery_app worker -Q tax_strategies,celery -l info &

# Frontend
cd frontend
npm run dev
```

> For local-only testing, point Pinecone at the local emulator / a dev index so the publish step doesn't touch the shared production namespace. The env flag is only relevant in deployed environments.

---

## 1. Seed the catalogue (one action)

```sh
# As a super-admin via curl (or click "Seed from CSV" in the admin UI):
curl -X POST http://localhost:8000/api/v1/admin/tax-strategies/seed-from-csv \
     -H "Authorization: Bearer $CLERK_JWT"
# → { "created": 415, "skipped": 0, "errors": [] }

# Re-run is a no-op:
curl -X POST http://localhost:8000/api/v1/admin/tax-strategies/seed-from-csv \
     -H "Authorization: Bearer $CLERK_JWT"
# → { "created": 0, "skipped": 415, "errors": [] }
```

Verify in the admin UI:
- Open `/admin/knowledge` → **Strategies** tab.
- Expect 415 rows, all `status=stub`, paginated 50 per page.
- Filter by category `Recommendations` — `CLR-012` appears.

---

## 2. Walk CLR-012 through the pipeline

Open `/admin/knowledge` → **Strategies** → search `CLR-012` → open the detail Sheet.

### 2a. Research

Click **Research**. Backend queues `tax_strategies.research` Celery task.
- In Phase 1, the worker loads the pre-populated ATO source list for this strategy from `backend/app/modules/tax_strategies/data/ato_source_fixtures.py` (CLR-012 and 2–3 other slice strategies are seeded there). Phase 2 replaces the fixture with live ATO scraping.
- Job row appears in the "Authoring jobs" section of the Sheet with `status=running`.
- A few seconds later the job row flips to `succeeded`; `output_payload.ato_sources` lists the loaded references.
- Strategy status transitions `stub → researching` (the Sheet refreshes automatically via TanStack Query).

### 2b. Draft

Click **Draft**. Backend queues `tax_strategies.draft`.
- LLM (Claude Sonnet) drafts `implementation_text` + `explanation_text` using the prompt in architecture §10.3, reading the fixture-loaded `ato_sources` from the research stage.
- On success, status flips to `drafted`. Implementation and explanation render read-only in the Sheet.

### 2c. Enrich

Click **Enrich**. Backend queues `tax_strategies.enrich`.
- Second LLM pass extracts structured eligibility metadata (entity_types, age bands, keywords, etc.).
- Status → `enriched`. Eligibility fields populate (still read-only in Phase 1).

### 2d. Submit for review

Click **Submit for review**. Synchronous API call, no Celery task.
- Status → `in_review`. Pipeline dashboard count shifts.

### 2e. Approve & publish

Click **Approve & publish**. This:
1. Transitions `in_review → approved`; captures reviewer identity from the Clerk JWT; sets `last_reviewed_at`; emits `tax_strategy.approved` audit event.
2. Queues `tax_strategies.publish`.

The publish task:
1. Chunks the strategy via `StrategyChunker` (exactly 2 chunks: implementation, explanation).
2. Prepends the `[CLR-012: Concessional super contributions — Category: Recommendations]` context header to each.
3. Appends the `Keywords: concessional, catch-up super, carry forward, ...` tail.
4. Embeds both chunks via `VoyageService`.
5. Checks the env gate: `vector_writes_enabled()`. If false → job fails with `vector_write_disabled_in_this_environment`, strategy stays `approved`. If true → proceeds.
6. Upserts 2 vectors to Pinecone namespace `tax_strategies` with IDs `tax_strategy:CLR-012:implementation:v1` and `tax_strategy:CLR-012:explanation:v1`.
7. Writes 2 `content_chunks` rows with `tax_strategy_id` FK, `chunk_section`, `context_header` populated.
8. Writes 2 `bm25_index_entries` rows.
9. Flips status to `published`; emits `tax_strategy.published` audit event with `{version: 1, chunk_count: 2, vector_store_env: "production"}`.

Admin Sheet refreshes to show `status=published`.

---

## 3. Verify retrieval

### 3a. Admin Search Test tab

Go to `/admin/knowledge` → **Search Test** → type query:

> `should my employee salary-sacrifice to super?`

In the namespace selector, include both `compliance_knowledge` and `tax_strategies`.

Expect a top result card:
- Source type: `tax_strategy`
- Strategy ID: `CLR-012`
- Category: `Recommendations`
- Chunk section: `implementation` or `explanation`
- "Open strategy" link that opens the admin detail Sheet.

### 3b. Tax planning chat (the headline moment)

Create a test tax plan (or open an existing one).

Ask:
> `should my employee salary-sacrifice to super?`

Expected response:
- Assistant message contains inline `[CLR-012: Concessional super contributions]` markup.
- Frontend renders this as a **green** `StrategyChip` (verified).
- Clicking the chip opens a Sheet with the full strategy content (implementation + explanation + ATO sources).
- Message-level `CitationBadge` shows something like:
  > "1 strategy cited (all verified) — 2 ATO sources referenced"

### 3c. Verify the red path

Manually inject a hallucinated `[CLR-999: Fake strategy]` into a test response (via the verifier unit test or a prompt-injection fixture):
- Chip renders **red** (unverified).
- Message badge shows partial verification.
- Chat response still renders cleanly.

### 3d. Verify the amber path

Inject `[CLR-012: Super contributions strategy]` (name drift ≥ 30% from `"Concessional super contributions"`):
- Chip renders **amber** (partially verified).

---

## 4. Developer-path smoke test (FR-030, SC-006)

Without touching the shared production namespace, run the fixture path:

```sh
cd backend
uv run pytest tests/integration/test_publish_roundtrip.py -v
```

This exercises a 3-strategy fixture that:
- Inserts 3 `TaxStrategy` rows at `status=approved` with pre-filled content.
- Runs `publish_strategy` against a local Pinecone index (not the shared namespace).
- Asserts 2 `content_chunks` per strategy, 2 BM25 entries per strategy, 2 vectors per strategy in the local index.
- Asserts `tax_strategy.published` audit events for each.
- Finally runs a retrieval query and asserts one of the fixtures comes back in the top 3.

Expected wall time: < 30s.

---

## 5. Rollback / teardown

```sh
# Archive the test strategy (reversible)
curl -X POST http://localhost:8000/api/v1/admin/tax-strategies/CLR-012/reject \
     -H "Authorization: Bearer $CLERK_JWT" \
     -d '{"reviewer_notes":"rolling back quickstart demo"}'

# Or, for a full local reset:
cd backend
uv run alembic downgrade -1   # reverts the Phase 1 migration
```

Note: downgrading the migration drops the two new tables and the three nullable columns on `content_chunks`. Existing non-strategy chunks are unaffected (their new columns are NULL).

---

## 6. What this quickstart proves

- **FR-001..FR-012** — schema, identifiers, lifecycle, pipeline, seed.
- **FR-013..FR-016** — chunking, retrieval wiring.
- **FR-020..FR-022** — citation markup, verification state rendering.
- **FR-023..FR-026** — admin surfaces.
- **FR-027..FR-030** — env gate, shared vector store, dev fixture path.
- **SC-001, SC-003, SC-004, SC-006, SC-007, SC-009** — all measurable from the walkthrough above.

Remaining success criteria (SC-002: 415 stubs seeded is proved by §1; SC-005: vector dedup across envs needs multi-env testing; SC-008: 415-row list loads under 500ms; SC-010: second live alpha session) are validated as part of Phase 1 exit acceptance outside this quickstart.
