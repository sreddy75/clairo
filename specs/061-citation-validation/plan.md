# Implementation Plan: Citation Substantive Validation

**Branch**: `061-citation-validation` | **Date**: 2026-04-18 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/061-citation-validation/spec.md`

## Summary

Strengthen the citation verifier's substantive guarantees so a hallucinated ruling ID cannot achieve the "verified" badge and a wrong-act-year section attribution is detected. Approach: extend the existing `CitationVerifier` with (a) a strong/weak match distinction driven by chunk `ruling_number` metadata rather than surface substring, (b) an act-year field captured from the section-citation extractor, compared against a new hand-curated YAML mapping of ~100 Australian tax-law sections. Unify the streaming vs non-streaming confidence-gate handling behind a shared helper using the resolved Q2=C hybrid rule (preserve content, clear scenarios, warning banner). Ship the unit-test safety net first (TDD per FR-009), then the behavioural changes. No DB, no frontend, no multi-agent pipeline changes.

## Technical Context

**Language/Version**: Python 3.12+ (backend only)
**Primary Dependencies**: `PyYAML` (already in the backend stack for config; confirm during implementation), existing `CitationVerifier` module, existing `SECTION_REF_PATTERN` / `RULING_REF_PATTERN` / `NUMBERED_CITATION_PATTERN` regexes in `backend/app/modules/knowledge/chunkers/base.py`
**Storage**: N/A — no DB schema changes. New authoritative mapping lives as a source-controlled YAML file under `backend/app/modules/knowledge/data/section_act_mapping.yaml` (directory does not exist today; will be created).
**Testing**: pytest + pytest-asyncio. New unit test file at `backend/tests/unit/modules/knowledge/retrieval/test_citation_verifier.py` (directory does not exist today; will be created). Existing e2e fixture test at `backend/tests/e2e/tax_planning/test_citation_regression_bank.py` MUST continue to pass unchanged.
**Target Platform**: Linux server (FastAPI + Celery in Docker). Verifier runs synchronously inside the tax planning service and the knowledge chatbot; no new infra.
**Project Type**: Single backend-module change (`knowledge` module) with one downstream touch (`tax_planning/service.py` for the parity helper).
**Performance Goals**: Per-citation verification ≤10ms for the strong-match path, ≤20ms when the section-act mapping is consulted (NFR-001). YAML loaded once at module import and cached in memory.
**Constraints**: Must preserve the Spec 059 `semantic=0` regression fix (FR-011); must not change `CitationVerificationResult` shape in any way existing consumers cannot ignore (FR-012 uses additive fields only).
**Scale/Scope**: ~100 Australian tax-law sections in the mapping initially, extensible via PR. Verifier processes 0–20 citations per LLM response; ~1–50 retrieved chunks per response.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular Monolith | ✅ Pass | Change is contained in the `knowledge` module (verifier + regex + data file) plus one helper extraction in `tax_planning/service.py`. No cross-module boundary violations. |
| II. Technology Stack | ✅ Pass | `PyYAML` already in the backend stack; no new deps. |
| III. Repository Pattern | N/A | No DB access in the verifier or the new mapping loader. |
| IV. Multi-Tenancy | ✅ Pass | Verifier is tenant-agnostic (operates on LLM output + retrieved chunks). Tenant context is upstream. |
| V. Testing Strategy | ✅ Pass | New unit-test suite (≥8 tests per FR-008), existing e2e regression preserved. TDD order enforced via FR-009 — tests land before the behavioural change. |
| VI. Code Quality | ✅ Pass | Type hints on all new/changed signatures; Pydantic model considered in research (R2). |
| VII. API Design | N/A | No HTTP API change. |
| VIII. External Integrations | ✅ Pass | No new external integrations. |
| IX. Security | ✅ Pass | No new secret handling. YAML is read-only, source-controlled, reviewable. |
| X. Auditing | ✅ Pass | Existing `tax_planning.citation.verification_outcome` audit event gains two additive metadata fields (`match_strength`, `reason_code`). No new event types, no retention change. |
| XI. AI/RAG Standards | ✅ Pass | Strengthens "AI suggests, human approves" by making the platform's confidence signal more trustworthy. Q2=C decision enforces this by always clearing scenarios on sub-threshold responses while preserving content for accountant review. |
| XII. Spec-Kit Process | ✅ Pass | Full speckit flow: specify → plan → tasks → implement. |

**Gate verdict**: PASS. No violations. Complexity tracking section omitted.

## Project Structure

### Documentation (this feature)

```text
specs/061-citation-validation/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── section_act_mapping.schema.yaml   # JSONSchema describing the mapping file structure
├── checklists/
│   └── requirements.md  # Already created by /speckit.specify
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       ├── knowledge/
│       │   ├── retrieval/
│       │   │   └── citation_verifier.py        # EDIT — add strong/weak match, act-year validation, reason_code
│       │   ├── chunkers/
│       │   │   └── base.py                     # EDIT — extend SECTION_REF_PATTERN to capture act-year suffix
│       │   └── data/                           # NEW directory
│       │       └── section_act_mapping.yaml    # NEW — curated mapping
│       └── tax_planning/
│           └── service.py                      # EDIT — extract shared sub-threshold-gate helper; unify streaming + non-streaming per Q2=C
└── tests/
    ├── unit/
    │   └── modules/
    │       └── knowledge/
    │           └── retrieval/
    │               └── test_citation_verifier.py   # NEW — unit-test safety net (≥8 tests)
    └── e2e/
        └── tax_planning/
            └── test_citation_regression_bank.py    # UNTOUCHED — MUST continue to pass
```

**Structure Decision**: Two module files edited (`citation_verifier.py`, `base.py`), one file extended in-place for the parity helper (`tax_planning/service.py`), one new data file (YAML), one new test file. Two new directories: `backend/app/modules/knowledge/data/` and `backend/tests/unit/modules/knowledge/retrieval/`. No cross-module boundary changes.

## Phase 0 Output: Research (`research.md` content)

### R1 — YAML loading: init-time cache vs per-request

**Decision**: Load the YAML once at module import and cache as a frozen dict keyed by normalised section identifier. Expose via a module-level function `get_section_act_mapping() -> Mapping[str, dict]`.

**Rationale**:
- The mapping is immutable at runtime — it only changes when a new PR lands a new entry. No value in re-reading per request.
- Per-citation latency budget is 10/20ms (NFR-001). A YAML parse per citation is wasted work.
- Module-level cache is the simplest pattern. Tests that need to override the mapping do so via `monkeypatch` on the module's cache or the accessor function.

**Alternatives considered**:
- Per-request reload — simpler reasoning but wasted I/O; no user-facing benefit.
- SQLite / embedded DB — overkill; a ~100-row lookup doesn't need query machinery.
- Environment-configurable path — unnecessary flexibility; the mapping ships with the codebase.

### R2 — Pydantic model for citation-result shape

**Decision**: Keep the citation verification result as a `TypedDict` with additive fields. Do NOT introduce a Pydantic model.

**Rationale**:
- Existing consumers (`service.py:1342`, audit log serialisation, UI rendering) read the result as a plain dict. A Pydantic model means every consumer needs a conversion step or pays validation cost per citation.
- FR-012's additive fields (`match_strength`, `reason_code`) are lint-checkable via TypedDict without runtime Pydantic overhead.
- Pydantic's value (runtime validation) is strongest at module boundaries (HTTP, LLM input). The verifier is fully internal — any bad dict shape is a code bug caught by tests, not a runtime input failure.

**Alternatives considered**:
- Pydantic model — rejected on overhead + consumer-migration cost.
- `@dataclass` — slightly better than TypedDict for IDE support but still changes consumer signatures.

### R3 — `reason_code` taxonomy shape

**Decision**: Closed enum (Python `enum.StrEnum`) with initial values:
- `strong_match` — metadata equality (not a failure; reported for observability parity)
- `weak_match_body_only` — identifier appears in chunk body text but not in chunk `ruling_number` metadata
- `weak_match_none` — identifier appears nowhere in retrieved chunks (hallucination)
- `wrong_act_year` — section correctly matched but act year misattributed per authoritative mapping
- `unknown_section` — section not in authoritative mapping; no act-year check performed (falls through to existing match logic)
- `no_citations` — response contained nothing the extractor recognised

**Rationale**:
- Closed enum makes the taxonomy part of the contract — consumers can pattern-match exhaustively.
- String-valued enum serialises cleanly to JSON (audit log, API, DB JSONB).
- Extensible via new enum members without breaking readers of older codes.

**Alternatives considered**:
- Open string — invites typos and undocumented codes drifting into the taxonomy.
- Integer codes — not human-readable in logs/DB.

### R4 — Parity helper location

**Decision**: Sub-threshold-gate parity helper is a private module-level function in `backend/app/modules/tax_planning/service.py` — not in the knowledge module.

**Rationale**:
- The helper's purpose is to normalise tax-planning-service-specific response handling (scenarios, response content, status label). Those are tax_planning concerns.
- The knowledge module produces the confidence signal; the tax_planning service decides what to DO with a sub-threshold signal. Keeping the decision in tax_planning preserves the separation.
- Both call sites already live in `service.py` (~1460-1482 non-streaming, ~1747-1760 streaming). Extracting a shared function in the same file is the smallest coherent refactor.

**Alternatives considered**:
- Helper in the knowledge module — wrong separation (knowledge produces signals; tax_planning consumes them).
- Middleware / decorator — over-engineering for two call sites.

### R5 — Integration with existing `matched_by` attribution (C-05 coexistence)

**Decision**: The new `match_strength` field lives alongside the existing `matched_by` field. They describe different dimensions:
- `match_strength`: how confidently the verifier believes the citation is real (metadata-equality vs body-mention vs miss).
- `matched_by`: which chunk field was used to make the match (observability attribution).

**Rationale**:
- C-05 (`matched_by` mislabel for numbered citations with populated `ruling_number`) is explicitly out of scope for this spec. The two fields serve different purposes and the audit log already consumes `matched_by`.
- `match_strength` is driven by the verifier's internal decision logic; `matched_by` is post-hoc attribution. Keeping them separate avoids entangling an intentional spec change with a known-deferred observability bug.

**Invariant (enforced + asserted by tests)**:
- `match_strength=strong` ⇒ `matched_by ∈ {ruling_number, section_ref}` (metadata paths).
- `match_strength=weak` ⇒ `matched_by ∈ {body_text, title, numbered_index}`.

**Alternatives considered**:
- Collapse `matched_by` into `match_strength` — breaks existing audit-log consumers.
- Leave them independent with no invariant — loses useful cross-check; future code could set strong + body_text which is a contradiction.

### R6 — YAML schema & seeding strategy

**Decision**: YAML structure is a flat mapping of normalised section identifier → metadata object. Schema in `contracts/section_act_mapping.schema.yaml`. Initial seeding is a hand-curated list of the top 100 sections by production citation frequency over the last 12 months; fallback if production log mining is impractical at implementation time, a human-curated list of the top frequently-cited tax-planning sections.

**Rationale**:
- Flat mapping is the simplest queryable shape. Hierarchical YAML (by act, by part) is harder to query and offers no benefit for 100 entries.
- Human-readable section identifiers as keys keep the file reviewable without tooling.
- Initial 100-section target covers the head of the long tail. Coverage grows via PR.

**Alternatives considered**:
- JSON — YAML's inline-comment support is valuable for the domain-expert reviewer.
- TOML — less familiar to tax-law reviewers.
- Database table — violates Constitution II (adds infrastructure for a 100-row lookup).

### R7 — Section identifier normalisation

**Decision**: Normalise section identifiers by: lowercasing; stripping whitespace; removing a leading `s`, `sec.`, or `section ` prefix; collapsing internal whitespace. Example: `"Section 82KZM"`, `"s 82KZM"`, `"S82KZM"`, `"sec. 82kzm"` all normalise to `"82kzm"`.

**Rationale**:
- LLM output is inconsistent about prefixes, case, whitespace. Normalising at lookup time avoids N spelling variants in the YAML.
- Pure function of the string — unit-testable in isolation.
- Same normaliser runs on YAML keys at load time and on incoming citation values at lookup — symmetric comparison.

**Alternatives considered**:
- Require exact match — too brittle against real LLM output.
- Approximate fuzzy match — adds false positives (e.g., `s82KZMD` vs `s82KZM`).

## Phase 1 Output: Design (`data-model.md` content)

### Extended extracted citation

```python
class ExtractedCitation(TypedDict):
    type: Literal["numbered", "section", "ruling"]
    value: str                       # Raw citation text as it appeared
    index: int | None                # For numbered citations only
    act_year: str | None             # NEW — captured act-year suffix, e.g. "ITAA 1997"; None if absent
```

### Extended citation verification result

```python
class CitationVerificationResult(TypedDict):
    # Existing fields — UNCHANGED
    number: int | None
    title: str
    url: str | None
    source_type: str
    section_ref: str
    effective_date: str | None
    text_preview: str
    score: float
    verified: bool

    # New fields — ADDITIVE, backward-compatible
    match_strength: Literal["strong", "weak", "none"]   # From R3
    reason_code: "CitationReasonCode"                   # StrEnum per R3
```

### Section → Act mapping (new persisted artefact, in-repo)

YAML structure (example excerpt):
```yaml
# backend/app/modules/knowledge/data/section_act_mapping.yaml
# Authoritative mapping of Australian tax-law section identifiers to their owning Act.
# Reviewed by domain experts. Extend via PR.

"82kzm":
  act: "ITAA 1936"
  display_name: "s 82KZM ITAA 1936"
  notes: "Prepayment provisions for non-business taxpayers"

"82kzmd":
  act: "ITAA 1936"
  display_name: "s 82KZMD ITAA 1936"

"328-180":
  act: "ITAA 1997"
  display_name: "s 328-180 ITAA 1997"
  notes: "SBE instant asset write-off"

# ... target: 100 entries at ship
```

Python shape after load + normalisation:
```python
SectionActMapping = Mapping[str, dict]   # normalised-section-id → {act, display_name, notes?}
```

### Validation rules (verifier behaviour)

1. **YAML loader (R1)**: On module import, read YAML; malformed → startup error (fail-fast). Normalise keys at load. Cache is a frozen mapping; tests override via `monkeypatch`.
2. **Act-year extractor (FR-004)**: Extended regex captures act-year suffix when present. Captured suffix normalised to closed set `{"ITAA 1997", "ITAA 1936", "TAA 1953", "GST Act 1999", "FBTAA 1986"}`. Unrecognised act kept as raw string.
3. **Act-year comparator (FR-005, FR-006)**: When `citation.act_year` is truthy AND section is in mapping, compare. Disagreement → `verified=False`, `reason_code=wrong_act_year`. Match OR either side unknown → skip act-year check, fall through to existing metadata/body-text match logic.
4. **Topical-relevance gate (FR-001–FR-003)**: For ruling citations, `verified=True` only when `chunk.ruling_number == citation.value` (normalised). Body-text mention only → `match_strength=weak`, `reason_code=weak_match_body_only`, `verified=False`. No match anywhere → `match_strength=none`, `reason_code=weak_match_none`, `verified=False`.

### Parity helper contract

```python
def _apply_subthreshold_gate(
    response_content: str,
    scenarios: list[dict],
    confidence_score: float,
    retrieved_chunks: list[dict],
) -> tuple[str, list[dict], str]:
    """Apply Q2=C hybrid rule when confidence is below threshold.

    Returns (response_content, scenarios, status_label). Rules:
      - If confidence >= 0.5 OR retrieved_chunks is empty: pass-through
        (response_content unchanged, scenarios unchanged, status_label="ok" or
        whatever the caller computed).
      - Sub-threshold (confidence < 0.5 AND retrieved_chunks non-empty):
          * response_content preserved verbatim (do NOT replace with canned decline)
          * scenarios replaced with empty list (cleared)
          * status_label = "low_confidence"
    """
```

Both streaming and non-streaming call sites in `tax_planning/service.py` invoke this helper. The streaming path threads the cleared scenarios into its post-completion persistence; the non-streaming path passes the tuple straight to its response builder.

### State transitions

None. Verifier is stateless; mapping is immutable at runtime.

## Phase 1 Output: Contracts

See `contracts/section_act_mapping.schema.yaml` — JSONSchema for the mapping file:
- Top-level: object; additional properties allowed (each property = one section entry).
- Entry value: object with required `act` (string), required `display_name` (string), optional `notes` (string).
- `act` is a string; closed-set validation happens in the Python loader (not schema-level) because the recognised-acts set may grow.

## Phase 1 Output: Quickstart (`quickstart.md` content)

### Verifying the implementation locally

1. **Unit tests** — fast, deterministic:
   ```sh
   cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py -v
   ```
   Expect: ≥8 tests pass covering extraction, match paths, act-year branches, YAML loader edge cases.

2. **E2E regression** — confirms Spec 059 `semantic=0` fix preserved:
   ```sh
   cd backend && uv run pytest tests/e2e/tax_planning/test_citation_regression_bank.py -v
   ```
   Expect: unchanged green (FR-011, SC-005).

3. **Static check — no blind-substring ruling match**:
   ```sh
   grep -n "response_text\b\|chunk_text\b" backend/app/modules/knowledge/retrieval/citation_verifier.py
   ```
   Expect: the ruling-citation match path checks metadata equality explicitly, not a bare `in` predicate on body text alone.

4. **Live smoke — single-mode**: trigger a chat query known to cite a ruling. Check the audit-log entry for that request — `tax_planning.citation.verification_outcome` metadata must include `match_strength` and `reason_code` per citation.

5. **Sub-threshold parity check**: trigger a query that scores below 0.5 confidence (off-topic with sparse retrieval). Compare streaming vs non-streaming:
   - Both preserve the LLM text response
   - Both persist zero scenarios
   - Both set `status=low_confidence`

### Agent context update

Run `.specify/scripts/bash/update-agent-context.sh claude` after plan lands to refresh the context file.

### Definition of done

- [ ] All new unit tests pass (≥8)
- [ ] E2E regression test passes unchanged
- [ ] Grep check on verifier confirms metadata-equality path for ruling citations
- [ ] YAML loads at import with ≥100 seeded entries
- [ ] Parity helper is called from both streaming and non-streaming paths in `service.py`
- [ ] Audit event `tax_planning.citation.verification_outcome` shows `match_strength` and `reason_code` on a live chat test

## Re-evaluation: Constitution Check (Post-Design)

| Principle | Status | Notes |
|-----------|--------|-------|
| I. Modular Monolith | ✅ Pass | Confirmed — two modules touched (`knowledge` for the verifier + data; `tax_planning` for the parity helper). No boundary violations. |
| V. Testing Strategy | ✅ Pass | TDD order explicit in FR-009. Unit tests land before behavioural change. E2E regression pinned. |
| VI. Code Quality | ✅ Pass | Type hints throughout; TypedDict + StrEnum additions lint-checkable. Pydantic deliberately not used per R2. |
| X. Auditing | ✅ Pass | Additive fields only on existing event; no schema change. |
| XI. AI/RAG Standards | ✅ Pass | Q2=C hybrid decision strengthens "AI suggests, human approves" by clearing sub-threshold scenarios while preserving content for review. |

**Post-design gate verdict**: PASS. No new violations.

## Complexity Tracking

*(Omitted — no constitution violations.)*
