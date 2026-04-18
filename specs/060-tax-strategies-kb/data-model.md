# Phase 1 Data Model — Tax Strategies KB (060)

Two new tables, two nullable columns on an existing table, one new Pinecone namespace, one in-repo CSV fixture. Alembic migration name: `2026xxxx_tax_strategies_phase1`.

---

## 1. New table: `tax_strategies`

Authoritative parent record. One row per strategy per version per tenant scope.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `uuid4()` | PK |
| `strategy_id` | VARCHAR(16) | no |  | Clairo identifier, e.g. `CLR-241`. Unique across all tenants within the **current** version; prior versions retained. |
| `source_ref` | VARCHAR(32) | yes |  | Internal-only (e.g. `STP-241`). Never returned by public endpoint (FR-008). |
| `tenant_id` | VARCHAR(64) | no | `"platform"` | `"platform"` for baseline; tenant UUID for Phase 3 overlays. Indexed. |
| `name` | VARCHAR(200) | no |  | Human-readable title. |
| `categories` | ARRAY(VARCHAR) | no | `[]` | Multi-tag from fixed taxonomy of 8 (FR-003). GIN-indexed. |
| `implementation_text` | TEXT | no | `""` | Empty string while `status='stub'`. |
| `explanation_text` | TEXT | no | `""` | Empty string while `status='stub'`. |
| `entity_types` | ARRAY(VARCHAR) | no | `[]` | GIN-indexed. |
| `income_band_min` | INTEGER | yes |  |  |
| `income_band_max` | INTEGER | yes |  |  |
| `turnover_band_min` | INTEGER | yes |  |  |
| `turnover_band_max` | INTEGER | yes |  |  |
| `age_min` | INTEGER | yes |  |  |
| `age_max` | INTEGER | yes |  |  |
| `industry_triggers` | ARRAY(VARCHAR) | no | `[]` | GIN-indexed. |
| `financial_impact_type` | ARRAY(VARCHAR) | no | `[]` | `deduction_expansion | tax_deferral | income_split | cgt_reduction | fbt_reduction | asset_protection | succession | retirement` |
| `keywords` | ARRAY(VARCHAR) | no | `[]` | GIN-indexed; tail-appended to chunks. |
| `ato_sources` | ARRAY(VARCHAR) | no | `[]` | e.g. `['ITAA 1997 Div 87', 'TR 2001/8']`. |
| `case_refs` | ARRAY(VARCHAR) | no | `[]` |  |
| `version` | INTEGER | no | `1` | Substantive change → new row with incremented version. |
| `status` | VARCHAR(32) | no | `"stub"` | Enum (see §1.2). Indexed. |
| `fy_applicable_from` | DATE | yes |  |  |
| `fy_applicable_to` | DATE | yes |  | Set when superseded. |
| `last_reviewed_at` | TIMESTAMPTZ | yes |  | Set at approval. |
| `reviewer_clerk_user_id` | VARCHAR(120) | yes |  | Snapshot of Clerk user ID at approval. |
| `reviewer_display_name` | VARCHAR(200) | yes |  | Snapshot of human-readable name at approval. |
| `superseded_by_strategy_id` | VARCHAR(16) | yes |  | Points at the replacement's `strategy_id`. |
| `created_at` | TIMESTAMPTZ | no | `now()` |  |
| `updated_at` | TIMESTAMPTZ | no | `now()` | `onupdate=now()`. |

### 1.1 Indexes

```
UNIQUE (strategy_id) WHERE superseded_by_strategy_id IS NULL
    -- only one live row per CLR-ID; older versions remain referenceable

GIN  (categories)
GIN  (entity_types)
GIN  (industry_triggers)
GIN  (keywords)
BTREE (tenant_id, status)
BTREE (status)            -- list-view filter
BTREE (source_ref)        -- internal lookup during seed idempotency check
```

### 1.2 Status enum

```
stub → researching → drafted → enriched → in_review → approved → published
                                                         │
                                                         └─ (failed publish) stays in `approved` with failed job row
published → superseded     (when a replacement version is published)
(any)     → archived       (manual kill)
```

Transitions are centralised in `TaxStrategyService._transition_status(old, new)`. The method:
1. Validates `(old, new)` is an allowed edge in the state machine (rejects `stub → published`, etc.).
2. Updates `updated_at`.
3. Emits `tax_strategy.status_changed` audit event.
4. On `in_review → approved`, additionally captures reviewer identity, sets `last_reviewed_at`, and emits `tax_strategy.approved`.
5. On `approved → published`, emits `tax_strategy.published` with the chunk count payload.

### 1.3 Invariants

- `strategy_id` follows regex `^CLR-\d{3,5}$`. Enforced by Pydantic schema.
- `source_ref` never returned by the public hydration endpoint (FR-008); router strips it explicitly.
- `version >= 1`.
- `superseded_by_strategy_id`, when non-null, must reference an existing live `strategy_id` (application-level check; not a FK because `strategy_id` alone isn't unique across versions).
- `implementation_text`, `explanation_text` non-empty when `status IN ('drafted', 'enriched', 'in_review', 'approved', 'published')`. Enforced at transition time.
- Categories list must be a non-empty subset of the fixed taxonomy (`Business`, `Recommendations`, `Employees`, `ATO_obligations`, `Rental_properties`, `Investors_retirees`, `Business_structures`, `SMSF`).

---

## 2. New table: `tax_strategy_authoring_jobs`

Per-stage pipeline execution tracker.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `id` | UUID | no | `uuid4()` | PK |
| `strategy_id` | VARCHAR(16) | no |  | Clairo identifier (not FK — references the live row's public identifier, not the UUID, for readability). Indexed. |
| `stage` | VARCHAR(32) | no |  | `research | draft | enrich | publish`. Indexed. |
| `status` | VARCHAR(32) | no | `"pending"` | `pending | running | succeeded | failed`. Indexed. |
| `started_at` | TIMESTAMPTZ | yes |  |  |
| `completed_at` | TIMESTAMPTZ | yes |  |  |
| `input_payload` | JSONB | no | `{}` |  |
| `output_payload` | JSONB | yes |  | Populated on success. |
| `error` | TEXT | yes |  | Populated on failure (includes the fixed error code `vector_write_disabled_in_this_environment` when the env gate blocks publish). |
| `triggered_by` | VARCHAR(120) | no |  | Clerk user ID of the super-admin who triggered the stage. |
| `created_at` | TIMESTAMPTZ | no | `now()` |  |

### 2.1 Indexes

```
BTREE (strategy_id, stage, created_at DESC)   -- per-strategy stage history for admin detail view
BTREE (status)                                 -- pipeline dashboard aggregations
BTREE (stage, status)                          -- "show all failed publish jobs"
```

### 2.2 Invariants

- A strategy may have multiple rows per `(strategy_id, stage)` (retries). The newest row (by `created_at`) is the current one.
- A publish job never leaves its strategy in a half-published state. On failure, the job row is marked `failed` with `error` populated and the strategy remains in `approved`. Retrying re-inserts a new publish job row.
- `output_payload.chunk_count` is populated on successful publish for audit.

---

## 3. Extensions to existing `content_chunks` table

Three new nullable columns. All backfill to NULL — existing ingestion paths unaffected.

| Column | Type | Null | Default | Notes |
|---|---|---|---|---|
| `tax_strategy_id` | UUID | yes |  | FK to `tax_strategies.id` with `ON DELETE CASCADE`. Indexed. NULL for all pre-existing chunks. |
| `chunk_section` | VARCHAR(32) | yes |  | `implementation | explanation | header` (Phase 1 uses first two only). NULL for non-strategy chunks. |
| `context_header` | VARCHAR(300) | yes |  | The prefix prepended to chunk text; stored for debuggability / re-chunking. NULL for non-strategy chunks. |

Existing columns reused unchanged:
- `content_type` = `"tax_strategy"`
- `collection_name` = `"tax_strategies"`
- `entity_types` (mirrored from parent on publish)
- `topic_tags` (mirrored from parent categories on publish)
- `is_superseded` (mirrors `TaxStrategy.status == 'superseded'`)
- `fy_applicable` (from parent)
- `natural_key` = `strategy_id` (e.g. `"CLR-241"`)
- `qdrant_point_id` = Pinecone vector ID (migration artefact; name preserved per project rules)

### 3.1 Migration safety

- All three additions are **nullable with NULL default** → no table rewrite on a large existing `content_chunks` table.
- No existing rows reference `tax_strategy_id`, so the FK check is trivially satisfied.
- No index changes beyond the new `tax_strategy_id` index itself.

---

## 4. Pinecone namespace: `tax_strategies`

Added to `NAMESPACES` dict in `backend/app/modules/knowledge/collections.py`:

```python
"tax_strategies": {
    "description": (
        "Clairo-authored Australian tax planning strategies. "
        "~415 entries across 8 categories. Platform-baseline; "
        "private overlays filtered via metadata tenant_id."
    ),
    "shared": True,  # single namespace across all envs
    "filterable_fields": [
        "tenant_id", "strategy_id", "categories", "chunk_section",
        "entity_types", "industry_triggers",
        "income_band_min", "income_band_max",
        "turnover_band_min", "turnover_band_max",
        "age_min", "age_max",
        "financial_impact_type",
        "fy_applicable_from", "fy_applicable_to",
        "is_superseded",
    ],
}
```

`shared=True` means the namespace has no environment suffix (unlike `insight_dedup`). All envs read from `"tax_strategies"`; only the env with `TAX_STRATEGIES_VECTOR_WRITE_ENABLED=true` writes to it.

### 4.1 Vector metadata schema (per chunk)

Identity:
```
chunk_id, tax_strategy_id, strategy_id, name, categories,
chunk_section, tenant_id, _collection="tax_strategies",
version, is_superseded,
fy_applicable_from, fy_applicable_to,
text   # chunk text (context header + body + keyword tail)
```

Structured eligibility (all optional; absent = broadly applicable):
```
entity_types, income_band_min, income_band_max,
turnover_band_min, turnover_band_max,
age_min, age_max, industry_triggers,
financial_impact_type, ato_sources, case_refs, keywords
```

### 4.2 Vector ID scheme

```
tax_strategy:{strategy_id}:{chunk_section}:v{version}
  e.g. tax_strategy:CLR-241:implementation:v1
```

Deterministic IDs make republish idempotent — the upsert overwrites the existing vector rather than creating a duplicate when the same version is re-published (FR-027: "MUST NOT re-embed for a strategy whose identifier and version already exist").

---

## 5. Seed fixture: `backend/app/modules/tax_strategies/data/strategy_seed.csv`

415 rows. Header:

```
strategy_id,name,categories,source_ref
```

Example rows:

```
CLR-001,Novated lease,Employees|Recommendations,STP-001
CLR-012,Concessional super contributions,Recommendations|Investors_retirees,STP-012
CLR-241,Change PSI to PSB,Business,STP-241
```

Categories are pipe-delimited to avoid CSV-within-CSV escaping. The seed action splits on `|`, validates each against the fixed taxonomy, and refuses the whole file on any unknown category.

### 5.1 Seed action contract (`seed_from_csv`)

```python
@dataclass
class SeedSummary:
    created: int
    skipped: int          # already existed with same strategy_id
    errors: list[str]     # invalid rows; entire seed fails if any present

async def seed_from_csv(
    csv_path: Path,
    triggered_by: str,
) -> SeedSummary: ...
```

- Transactional: either all valid rows insert or none do.
- Idempotent: `strategy_id` uniqueness (partial index on live version) causes duplicates to be skipped.
- Emits `tax_strategy.seed_executed` once per run with `{created, skipped, errors_count}`.
- Emits `tax_strategy.created` per inserted row.

---

## 6. Key relationships

```
tax_strategies (1) ──< (many) content_chunks         via tax_strategy_id
tax_strategies (1) ──< (many) tax_strategy_authoring_jobs  via strategy_id (logical FK)
tax_strategies (1) ──< (many) bm25_index_entries     via content_chunks (indirect)
```

No FK from `content_chunks.tax_strategy_id` to `tax_strategies.id` forces a rewrite — it's additive-nullable. Cascade delete is set so that deleting a strategy (rare, typically via archive instead) cleans up chunks.

---

## 7. What stays out of Phase 1

- Per-tenant overlay exercise (only `tenant_id="platform"` used in Phase 1 — schema ready, feature flagged off).
- Version-history diff view (detail view shows row-per-version; rich diff is Phase 2).
- Editable fields (markdown editors, eligibility form controls) — Phase 2.
- Annual ATO-source-change detection task — Phase 4.
