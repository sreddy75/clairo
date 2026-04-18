# Phase 1 Data Model: Citation Substantive Validation

**Feature**: Citation Substantive Validation
**Date**: 2026-04-18
**Scope**: Internal data shapes + one new source-controlled YAML artefact. No database entities, no persisted schema changes, no API contract changes.

---

## Overview

Three data shapes matter:

- **ExtractedCitation** (existing, one field added) — the structured output of the citation extractor.
- **CitationVerificationResult** (existing, two fields added) — the output of the verifier per citation. Downstream consumers see these additively.
- **SectionActMapping** (new) — authoritative lookup from section identifier → owning Act, seeded from a hand-curated YAML file.

Plus one new function contract:
- **`_apply_subthreshold_gate`** — the parity helper unifying streaming and non-streaming sub-threshold handling (Q2=C).

All changes are additive or internal-only. Zero breaking changes.

---

## Entity 1: ExtractedCitation (extended)

**Source**: Output of the extractor in `backend/app/modules/knowledge/retrieval/citation_verifier.py` (regexes from `chunkers/base.py`).
**Lifetime**: In-memory inside `CitationVerifier.verify_citations`. Never persisted as `ExtractedCitation`; only the downstream `CitationVerificationResult` reaches persistence.

| Field | Type | Required | Notes |
|-------|------|----------|-------|
| `type` | `Literal["numbered", "section", "ruling"]` | ✅ | Which regex matched. |
| `value` | `str` | ✅ | Raw citation text as it appeared in the response. |
| `index` | `int \| None` | optional | Set for `numbered` only. |
| `act_year` | `str \| None` | **NEW** | Captured act-year suffix (e.g. `"ITAA 1997"`, `"ITAA 1936"`); `None` if the citation carries no explicit act. Populated by the extended `SECTION_REF_PATTERN` for `type="section"` only. |

### Normalisation rules

- `value` is stored as raw LLM text for provenance. Comparisons use a normalised form (see R7 in research.md).
- `act_year`, when present, is normalised to one of the closed set `{"ITAA 1997", "ITAA 1936", "TAA 1953", "GST Act 1999", "FBTAA 1986"}`. Unrecognised acts (e.g. `"ITAA 2017"`) are preserved as the raw captured string and handled by the unknown-act edge case.

---

## Entity 2: CitationVerificationResult (extended)

**Source**: Output of `CitationVerifier._build_citation_dict` and its wrapper in `tax_planning/service.py:1283+`.
**Lifetime**: Per-citation dict, aggregated into a per-response `CitationVerificationResult` object (pre-existing shape from `citation_verifier.py:24-36`). Persisted on `tax_plan_messages.citation_verification` JSONB column and logged to audit events.

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `number` | `int \| None` | unchanged | For numbered citations. |
| `title` | `str` | unchanged | From matched chunk. |
| `url` | `str \| None` | unchanged | From matched chunk. |
| `source_type` | `str` | unchanged | From matched chunk. |
| `section_ref` | `str` | unchanged | From matched chunk. |
| `effective_date` | `str \| None` | unchanged | From matched chunk. |
| `text_preview` | `str` | unchanged | From matched chunk. |
| `score` | `float` | unchanged | Per-citation confidence (from chunk's `relevance_score`). |
| `verified` | `bool` | unchanged **semantics** | Now driven by the strong/weak match decision — metadata-equality required for `True` on ruling citations. |
| `matched_by` | `str` | unchanged | Existing observability field (`ruling_number`, `section_ref`, `title`, `body_text`, `numbered_index`, `unverified`). |
| `match_strength` | `Literal["strong", "weak", "none"]` | **NEW** | How the verifier classified the match. |
| `reason_code` | `CitationReasonCode` (StrEnum) | **NEW** | Machine-readable reason (see `CitationReasonCode` below). |

### New StrEnum: `CitationReasonCode`

```python
class CitationReasonCode(StrEnum):
    STRONG_MATCH = "strong_match"
    WEAK_MATCH_BODY_ONLY = "weak_match_body_only"
    WEAK_MATCH_NONE = "weak_match_none"
    WRONG_ACT_YEAR = "wrong_act_year"
    UNKNOWN_SECTION = "unknown_section"
    NO_CITATIONS = "no_citations"
```

### Invariant between `match_strength` and `matched_by`

- `match_strength == "strong"` ⇒ `matched_by ∈ {"ruling_number", "section_ref"}` (metadata paths).
- `match_strength == "weak"` ⇒ `matched_by ∈ {"body_text", "title", "numbered_index"}`.
- `match_strength == "none"` ⇒ `matched_by == "unverified"`.

Unit tests assert this invariant explicitly.

### Backward compatibility

Existing consumers:
- `service.py:1342` — writes per-citation dict. Will pass through the new fields unchanged.
- `service.py:1489-1492`, `:1786-1789` — aggregate `matched_breakdown`. New fields are additive; no change required to the aggregation logic, but the audit-log metadata dict gains the new keys (additive).
- Frontend rendering — will ignore unknown keys today; can opt in to the new reason codes in a later spec.
- `tax_plan_messages.citation_verification` JSONB — already permissive; new keys appear without migration.

---

## Entity 3: SectionActMapping (new, in-repo)

**Source**: Hand-curated YAML at `backend/app/modules/knowledge/data/section_act_mapping.yaml`. Loaded once at module import, cached in memory.

### YAML structure

Top-level is a flat mapping. Each key is a normalised section identifier (lowercased, no `s`/`section ` prefix). Each value is an object with at minimum `act` and `display_name`.

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

"6-5":
  act: "ITAA 1997"
  display_name: "s 6-5 ITAA 1997"
  notes: "Ordinary income derivation"

"177a":
  act: "ITAA 1936"
  display_name: "s 177A ITAA 1936"
  notes: "Part IVA general anti-avoidance scheme definition"

# ... target: 100 entries at ship
```

### Python shape after load

```python
SectionActMapping = Mapping[str, dict]   # normalised-section-id → {"act": str, "display_name": str, "notes": str | None}
```

### Validation rules at load time

- YAML parse failure → startup error (fail-fast, module import raises).
- Missing required field (`act` or `display_name`) → startup error with line pointer.
- Unknown `act` value → startup warning logged; entry retained for eventual match (defensive, not blocking).
- Duplicate key after normalisation → startup error (ambiguity).

### Access pattern

```python
from app.modules.knowledge.data.section_act_mapping import get_section_act_mapping

mapping = get_section_act_mapping()          # Returns cached Mapping[str, dict]
normalised_section = normalise_section("s82KZM")  # "82kzm"
entry = mapping.get(normalised_section)      # None if unknown
if entry and entry["act"] != citation.act_year:
    # Wrong-act-year case
    ...
```

### Test-time override

Tests monkeypatch `get_section_act_mapping` to return a controlled dict, isolating test data from the production YAML.

---

## Function contract: `_apply_subthreshold_gate`

**Location**: `backend/app/modules/tax_planning/service.py` (new private module-level function).

```python
def _apply_subthreshold_gate(
    response_content: str,
    scenarios: list[dict],
    confidence_score: float,
    retrieved_chunks: list[dict],
) -> tuple[str, list[dict], str]:
    """Apply the Q2=C hybrid rule when confidence is below threshold.

    Returns (response_content, scenarios, status_label).

    Rules:
    - If confidence_score >= 0.5 OR retrieved_chunks is empty:
        pass-through. Returns (response_content, scenarios, "ok").
    - Sub-threshold (confidence_score < 0.5 AND retrieved_chunks non-empty):
        * response_content preserved verbatim (NO canned decline replacement)
        * scenarios replaced with empty list (cleared)
        * status_label = "low_confidence"
    """
```

### Call sites

- `service.py` non-streaming path (~lines 1460-1482): replaces the current inline block.
- `service.py` streaming path (~lines 1747-1760): replaces the current inline block.

Both paths call the helper with the same signature. The streaming path threads the returned cleared-scenarios list into its post-completion persistence; the non-streaming path passes the full tuple to its response builder.

### Invariants

- Pure function: no side effects, no I/O.
- Idempotent: calling twice with the same inputs yields the same outputs.
- No dependency on the streaming/non-streaming distinction — the caller owns transport concerns.

---

## Data-flow diagram

```
LLM response text  ───▶  extract_citations()  ─┬─▶  ExtractedCitation[]
                                                │
chunk list  ────────────────────────────────────┤
                                                │
                                                ▼
                        CitationVerifier.verify_citations()
                              │
                              ├─▶ _find_chunk_for_reference()
                              │       │
                              │       ├─▶ topical-relevance gate (R1, FR-001..003)
                              │       │      ├─ metadata equality → match_strength=strong
                              │       │      ├─ body-text only    → match_strength=weak
                              │       │      └─ no hit            → match_strength=none
                              │       │
                              │       └─▶ act-year comparator (R5, FR-004..006)
                              │              ├─ mapping hit + disagree → wrong_act_year
                              │              ├─ mapping hit + agree    → pass through
                              │              └─ no mapping entry       → unknown_section
                              │
                              └─▶ CitationVerificationResult[]  ──▶  service.py wrapper  ──▶  audit + DB
```

Separately, at the chat-response level:

```
tax_plan message  ──▶  confidence_score computed  ──▶  _apply_subthreshold_gate()
                                                         │
                                                         ├─ above threshold → pass-through
                                                         └─ below threshold → (content kept,
                                                                                scenarios cleared,
                                                                                status=low_confidence)
                                                         │
                                                         ▼
                                     same outcome on streaming AND non-streaming paths
```

---

## Summary

- 1 existing shape (`ExtractedCitation`) gets 1 new optional field (`act_year`).
- 1 existing shape (`CitationVerificationResult`) gets 2 new additive fields (`match_strength`, `reason_code`).
- 1 new `StrEnum` (`CitationReasonCode`).
- 1 new in-repo YAML artefact (`section_act_mapping.yaml`) with ~100 entries at ship, PR-extensible.
- 1 new module-level function (`_apply_subthreshold_gate`) for streaming/non-streaming parity.
- Zero database changes, zero API contract changes, zero frontend changes.
