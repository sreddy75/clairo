# Phase 0 Research: Citation Substantive Validation

**Feature**: Citation Substantive Validation
**Date**: 2026-04-18
**Status**: Complete — all decisions below resolved; no open `NEEDS CLARIFICATION` markers

---

## R1 — YAML loading: init-time cache vs per-request

**Decision**: Load the YAML once at module import and cache as a frozen dict keyed by normalised section identifier. Expose via a module-level function `get_section_act_mapping() -> Mapping[str, dict]`.

**Rationale**:
- The mapping is immutable at runtime — it only changes when a new PR lands a new entry. No value in re-reading per request.
- Per-citation latency budget is 10/20ms (NFR-001). A YAML parse per citation is wasted work.
- Module-level cache is the simplest pattern. Tests override the mapping via `monkeypatch` on the accessor function or the cached module attribute.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Per-request reload | Wasted I/O; no user-facing benefit. |
| SQLite / embedded DB | Overkill for a 100-row lookup; violates Constitution II (no new infra for small problems). |
| Environment-configurable path | Unnecessary flexibility; the mapping ships with the codebase and is domain-reviewable. |

---

## R2 — Pydantic model for citation-result shape

**Decision**: Keep the citation verification result as a `TypedDict` with additive fields. Do NOT introduce a Pydantic model.

**Rationale**:
- Existing consumers (`service.py:1342`, audit log serialisation, UI rendering) read the result as a plain dict. A Pydantic model means every consumer pays a conversion / validation cost per citation.
- FR-012's additive fields are lint-checkable via TypedDict without runtime Pydantic overhead.
- Pydantic's value is strongest at module boundaries (HTTP, LLM input). The verifier is fully internal — any bad dict shape is a code bug caught by unit tests.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Pydantic model | Overhead + migration cost on all consumers for no correctness gain. |
| `@dataclass` | Changes consumer signatures; same migration cost. |

---

## R3 — `reason_code` taxonomy shape

**Decision**: Closed enum (`enum.StrEnum`) with initial values:

| Code | Meaning |
|------|---------|
| `strong_match` | Metadata equality (observability reporting; not a failure) |
| `weak_match_body_only` | Identifier in body text but not in chunk metadata |
| `weak_match_none` | Identifier absent from all retrieved chunks (hallucination) |
| `wrong_act_year` | Section correctly matched but act year misattributed per authoritative mapping |
| `unknown_section` | Section not in authoritative mapping; act-year check skipped |
| `no_citations` | Response contained nothing the extractor recognised |

**Rationale**:
- Closed enum makes the taxonomy part of the contract — consumers can pattern-match exhaustively.
- String-valued serialises cleanly to JSON (audit log, API, DB JSONB).
- Extensible via new members in later specs without breaking older readers.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Open string | Invites typos and undocumented codes drifting into the taxonomy. |
| Integer codes | Not human-readable in logs/DB. |

---

## R4 — Parity helper location

**Decision**: Sub-threshold-gate parity helper is a private module-level function in `backend/app/modules/tax_planning/service.py` — not in the knowledge module.

**Rationale**:
- The helper's purpose is tax-planning-service-specific response handling (scenarios, response content, status label). Those are tax_planning concerns.
- The knowledge module produces the confidence signal; the tax_planning service decides what to DO with a sub-threshold signal. Keeping the decision in tax_planning preserves separation of concerns.
- Both call sites already live in `service.py` (~lines 1460-1482 non-streaming, ~1747-1760 streaming). Extracting a shared function in the same file is the smallest coherent refactor.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Helper in knowledge module | Wrong separation (knowledge produces signals; tax_planning consumes them). |
| Middleware / decorator | Over-engineering for two call sites. |

---

## R5 — Integration with existing `matched_by` attribution

**Decision**: The new `match_strength` field lives alongside the existing `matched_by` field. They describe different dimensions:
- `match_strength`: confidence that the citation is real (metadata-equality vs body-mention vs miss).
- `matched_by`: which chunk field was used to make the match (observability attribution, pre-existing).

**Invariant (enforced + asserted by tests)**:
- `match_strength=strong` ⇒ `matched_by ∈ {ruling_number, section_ref}` (metadata paths).
- `match_strength=weak` ⇒ `matched_by ∈ {body_text, title, numbered_index}`.

**Rationale**:
- C-05 (known `matched_by` mislabel for numbered citations with populated `ruling_number`) is explicitly out of scope. Keeping the two fields separate avoids entangling this spec's intentional changes with that deferred observability bug.
- `match_strength` is driven by the verifier's decision logic; `matched_by` is post-hoc attribution. Different lifecycles warrant different fields.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Collapse `matched_by` into `match_strength` | Breaks existing audit-log consumers. |
| No invariant between the two | Loses cross-check; future code could set `strong + body_text` which is a contradiction. |

---

## R6 — YAML schema & seeding strategy

**Decision**: YAML structure is a flat mapping of normalised section identifier → metadata object. Schema in `contracts/section_act_mapping.schema.yaml`. Initial seeding: hand-curated list of the top ~100 Australian tax-law sections by production citation frequency over the preceding 12 months. Fallback if production log mining is impractical at implementation time: a domain-expert-reviewed list of frequently-cited tax-planning sections.

**Rationale**:
- Flat mapping is the simplest queryable shape. Hierarchical YAML (by act, by part) is harder to query for no benefit at this scale.
- Human-readable keys keep the file reviewable without tooling.
- 100 initial entries covers the head of the long tail. Growth via PR as new sections appear in traffic or UAT.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| JSON | YAML's inline comments are valuable for domain-expert review annotations. |
| TOML | Less familiar to tax-law reviewers. |
| Database table | Violates Constitution II (infrastructure for a 100-row lookup). |

---

## R7 — Section identifier normalisation

**Decision**: Normalise by: lowercasing; stripping whitespace; removing a leading `s`, `sec.`, or `section ` prefix; collapsing internal whitespace.

Examples (all normalise to `"82kzm"`):
- `"Section 82KZM"`
- `"s 82KZM"`
- `"S82KZM"`
- `"sec. 82kzm"`

**Rationale**:
- LLM output is inconsistent about prefixes, case, whitespace. Normalising at lookup time avoids N spelling variants in the YAML.
- Pure function of the string — unit-testable in isolation.
- Same normaliser runs on YAML keys at load time and on incoming citations at lookup — symmetric comparison.

**Alternatives**:

| Alternative | Why rejected |
|---|---|
| Require exact match | Too brittle against real LLM output. |
| Approximate fuzzy match | Adds false positives (e.g., `s82KZMD` vs `s82KZM`). |

---

## Open questions

None. All decisions resolved. Q1 and Q2 from the spec's Clarifications section were answered at spec time (Q1=A hand-curated YAML, Q2=C hybrid). Proceeding to Phase 1 design.
