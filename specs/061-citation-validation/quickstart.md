# Quickstart: Verifying the Citation Substantive Validation Implementation

**Feature**: Citation Substantive Validation (061)
**Audience**: Engineers landing or reviewing the implementation

---

## Prerequisites

- Docker Compose stack running (`docker-compose up -d`)
- `uv` installed (backend Python tooling)
- A tax plan exists in local DB with at least one completed analysis (use KR8 IT or any golden-dataset client)

---

## 1. Unit tests (no Docker required)

Fast, deterministic, YAML mapping monkeypatched to a small fixture.

```sh
cd backend && uv run pytest tests/unit/modules/knowledge/retrieval/test_citation_verifier.py -v
```

**Expect**: ≥8 tests pass covering:

| Test class | Coverage |
|------------|----------|
| extraction | numbered, section, ruling patterns — and the new `act_year` capture |
| ruling match | strong (metadata equality), weak (body only), none (no hit anywhere) |
| section match + act-year | correct Act → verify, wrong Act → `wrong_act_year`, unknown section → `unknown_section` |
| invariant | `match_strength` ↔ `matched_by` invariant (R5) |

Coverage target: ≥85% on `citation_verifier.py` (SC-003).

---

## 2. E2E regression — confirms Spec 059 fix preserved

```sh
cd backend && uv run pytest tests/e2e/tax_planning/test_citation_regression_bank.py -v
```

**Expect**: unchanged green. This test pins the `semantic=0` fix from Spec 059. FR-011 forbids any change in 061 that breaks it.

---

## 3. Static check — ruling citations no longer blind-substring match

```sh
grep -n "response_text\b\|chunk_text\b" backend/app/modules/knowledge/retrieval/citation_verifier.py
```

**Expect**: the ruling-citation match path checks chunk metadata (`ruling_number`) equality explicitly. Bare `in response_text` / `in chunk_text` predicates as the sole authority for verification should not appear.

A softer check — `ruling_number` appears in the file:

```sh
grep -c "ruling_number" backend/app/modules/knowledge/retrieval/citation_verifier.py
```

**Expect**: > 0 (confirming the metadata-equality path exists).

---

## 4. YAML loads at import — section→act mapping present

```sh
cd backend && uv run python -c "
from app.modules.knowledge.data.section_act_mapping import get_section_act_mapping
m = get_section_act_mapping()
print(f'Loaded {len(m)} entries')
print('Sample:', list(m.items())[:3])
"
```

**Expect**: ≥100 entries (SC-006), sample shows well-formed `{"section_id": {"act": ..., "display_name": ..., ...}}` tuples.

---

## 5. Live smoke — chat query with a cited response

Trigger a tax planning chat query known to produce a cited response (e.g. "Tell me about prepayment provisions for SBE clients").

In the DB (after the response completes):

```sh
docker exec clairo-postgres psql -U clairo -d clairo -c \
  "SELECT citation_verification->'citations' FROM tax_plan_messages ORDER BY created_at DESC LIMIT 1;"
```

**Expect**: each citation object carries `match_strength` and `reason_code` keys alongside existing `verified`/`matched_by`.

---

## 6. Sub-threshold parity check

Trigger a query that scores below the 0.5 confidence gate (off-topic question with sparse retrieval). Compare streaming vs non-streaming for the same input:

| Observable | Streaming | Non-streaming |
|---|---|---|
| LLM text response | preserved | preserved |
| Persisted scenarios on message | `[]` | `[]` |
| Status label | `low_confidence` | `low_confidence` |

**Expect**: all three rows match between the two modes (FR-010, SC-004).

---

## 7. Audit log enrichment

```sh
docker exec clairo-postgres psql -U clairo -d clairo -c \
  "SELECT metadata->'match_strength_breakdown', metadata->'reason_codes' \
   FROM audit_logs \
   WHERE event_type='tax_planning.citation.verification_outcome' \
   ORDER BY created_at DESC LIMIT 1;"
```

**Expect**: new aggregate fields populated. Pre-existing `matched_by_breakdown` and `confidence_score` remain untouched.

---

## Agent context update

After the plan lands:

```sh
.specify/scripts/bash/update-agent-context.sh claude
```

---

## Definition of done

- [ ] All new unit tests pass (≥8)
- [ ] E2E regression test passes unchanged
- [ ] Grep check: metadata-equality path for ruling citations present in verifier
- [ ] YAML loads at import with ≥100 seeded entries
- [ ] Parity helper `_apply_subthreshold_gate` is called from both streaming and non-streaming paths in `service.py`
- [ ] Audit event `tax_planning.citation.verification_outcome` shows `match_strength` and `reason_code` on a live chat test
- [ ] Section→act mapping reviewed by a domain expert (flag on PR)
- [ ] HANDOFF.md / briefs updated — move the citation brief from `specs/briefs/` status to "spec-in-progress" or delete if superseded
