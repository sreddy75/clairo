# Brief: Citation Substantive Validation (Tax Planning)

**Date**: 2026-04-18
**Source**: 059-2 live UAT run (KR8 IT, $24,375 tax plan) — reviewer's citation findings
**Author**: Suren + codebase audit of `backend/app/modules/knowledge/retrieval/citation_verifier.py`
**Related**: Supersedes the "Story 6" line item from HANDOFF.md (the original `semantic=0` bug was already resolved under Spec 059 — this brief documents the *new* gaps surfaced by 059-2 UAT).

---

## Problem Statement

The live-run 059-2 UAT produced an arithmetically correct tax plan ($24,375 Total Tax Saving, reviewer-verified). The reviewer still flagged the plan as "Needs Review" — but for **substantive citation issues**, not arithmetic. Two distinct defects appeared:

1. **Possibly-fabricated rulings slip through.** The reviewer wrote: *"TR 2012/8 cannot be confirmed as a real ATO ruling on prepayments and may be fabricated."* The citation verifier's match logic (`citation_verifier.py:228-247`) uses pure substring containment against chunk metadata and body text. If any retrieved chunk — on any topic — happens to mention the string "TR 2012/8", the ruling is marked `verified=True`. There is no topical-relevance check tying the ruling identifier to the chunk's subject matter. A hallucinated ruling identifier that happens to appear as a cross-reference somewhere in the knowledge base will pass.

2. **Wrong-act-year misattribution is invisible by design.** The reviewer wrote: *"the prepaid expenditure provisions are incorrectly attributed to ITAA 1997 when s 82KZM and s 82KZMD are ITAA 1936 provisions."* The extraction regex `SECTION_REF_PATTERN` at `knowledge/chunkers/base.py:34-40` captures only the section number token (e.g., `s82KZM`), discarding the act year suffix. The downstream comparator at `citation_verifier.py:228-247` never examines which act the section is attributed to. No field on either the citation side or the chunk side records the act name, so the verifier cannot catch a wrong-act citation — not a bug in the code path that exists, but an absence of any code path for this class of error.

Both defects are quality-of-citation problems, not arithmetic problems. The arithmetic fix from 059-2 was necessary but not sufficient: an accountant reading $24,375 out loud to a client will still be exposed if the supporting citation says "ITAA 1997 s 82KZM" when the correct attribution is "ITAA 1936 s 82KZM." PI insurance cares about both.

### What is NOT broken (already fixed)

- The original `semantic=0` / `dict-key typo` bug is **fixed**. See fix-comment at `service.py:1457-1459`: confidence scoring now reads `relevance_score` (the correct key) instead of `score` (the old missing key). There is a regression test for this at `tests/e2e/tax_planning/test_citation_regression_bank.py:97`. Do not re-open this.
- The substring-match brittleness ("section_ref metadata narrower than cited text") is mitigated by the body-text fallback at `citation_verifier.py:244-247`. Still imperfect but no longer the primary failure mode.

---

## Users

- **Primary**: Registered tax agents reading tax plan output to clients. They need citations they can defend against ATO review.
- **Secondary**: Accountants using the AI chat in knowledge/chatbot (same verifier is wired in at `chatbot.py:642`).

---

## Identified Issues

### C-01 — No topical-relevance gate on ruling citations

**Location**: `backend/app/modules/knowledge/retrieval/citation_verifier.py:199-249` (`_find_chunk_for_reference`).

**Symptom**: A hallucinated ruling ID passes verification if the identifier string appears anywhere in any retrieved chunk, regardless of whether the chunk is actually about that ruling.

**Current behaviour**: `verified=True` if `ref_lower in chunk_text` or `section_ref in ref_lower` or normalised ref in section_ref.

**Proposed direction (not prescriptive)**: Require that the matched chunk's `ruling_number` field exactly equals the cited ruling, OR the chunk's own title references it. Body-text cross-mentions are evidence of relationship, not authority. Separate "strong match" (metadata equality) from "weak match" (body-text mention) in the verified output.

### C-02 — No act-year validation on section citations

**Location**: `backend/app/modules/knowledge/chunkers/base.py:34-40` (extraction regex), `citation_verifier.py:228-247` (comparator). Both are act-year-blind.

**Symptom**: "s 82KZM ITAA 1997" verifies identically to "s 82KZM ITAA 1936" — neither the extractor nor the comparator captures or checks the act year.

**Proposed direction (not prescriptive)**: Extend the section-ref extractor to capture the act year as an explicit field. Add an authoritative section→act lookup (or require chunks to carry `act_name` metadata), and flag mismatches as `verified=False` with reason `wrong_act_year`. This is the class of check the verifier does not have today; adding it is new feature work, not a bug fix.

### C-03 — No unit tests on `CitationVerifier` directly

**Location**: `backend/tests/` — only one e2e fixture test (`test_citation_regression_bank.py`) covers the gate through the full service.

**Symptom**: Every branch in `_extract_citations_from_response`, `_find_chunk_for_reference`, and `_build_citation_dict` is untested. Regression risk is high for any change to the verifier.

**Proposed direction**: Unit tests covering each extraction pattern (numbered, section, ruling) and each match path (metadata hit, body-text hit, miss) before any change to C-01 or C-02 lands.

### C-04 — Streaming vs non-streaming confidence-gate divergence

**Location**: `service.py:1460-1482` (non-streaming) vs `service.py:1747-1760` (streaming).

**Symptom**: Below the 0.5 confidence threshold, the non-streaming path replaces the LLM response with the canned decline message and clears scenarios. The streaming path sets the same `low_confidence` status but does NOT overwrite content or clear scenarios — so a low-confidence answer is still shown to the user in streaming mode. Silent UX divergence.

**Proposed direction**: Apply the same guard in both paths. Likely 5-10 lines.

### C-05 — `_infer_matched_by` for numbered citations can mislabel

**Location**: `service.py:34-63` + `citation_verifier.py:272-282`.

**Symptom**: For a numbered-citation `[3]` whose matched chunk happens to carry `ruling_number` / `section_ref` populated, `_infer_matched_by` can return `ruling_number` or `section_ref` instead of `numbered_index`. Audit attribution is wrong; minor observability bug.

**Proposed direction**: Have `CitationVerifier` return `matched_by` directly in the result, rather than post-hoc re-derivation in service.py. Dead code removal once that lands.

---

## Priorities

| Issue | Blocks UAT? | Effort |
|-------|-------------|--------|
| C-01 — topical relevance gate | Yes (directly causes false-verified rulings) | Medium |
| C-02 — act-year validation | Yes (wrong-act citations are PI-exposure) | Medium-large (needs lookup data) |
| C-03 — unit tests | Prerequisite for C-01/C-02 | Small |
| C-04 — streaming divergence | No (quiet bug, not seen in UAT yet) | Small |
| C-05 — matched_by attribution | No (observability only) | Small |

Recommended sequencing: **C-03 → C-01 → C-02 → C-04/C-05 (opportunistic)**. C-03 is a prerequisite — any change to C-01 or C-02 without unit coverage is regression-unsafe.

---

## Success Criteria

- **SC-A**: A hallucinated ruling ID not present in any chunk's `ruling_number` metadata MUST be flagged `verified=False`, regardless of surface mentions elsewhere.
- **SC-B**: A citation of "s 82KZM ITAA 1997" MUST be flagged as wrong-act-year (the section belongs to ITAA 1936). A citation of "s 82KZM ITAA 1936" MUST verify.
- **SC-C**: Unit test coverage on `CitationVerifier.verify_citations` hits every `type` path (numbered, section, ruling) and every match path (metadata, body, miss) — minimum 8 tests, all <100ms.
- **SC-D**: Streaming and non-streaming confidence gates have observable parity — below 0.5 either both replace content + clear scenarios, or both preserve content + surface a warning banner. One consistent rule, not two.

---

## Out of Scope

- The `semantic=0` dict-key typo (fixed under 059).
- Citation formatting / presentation in the accountant brief PDF (visual concern, not verification).
- RAG retrieval quality itself (retrieved-chunk ranking is a separate spec — this brief is about verifying the LLM's citations against whatever chunks were actually retrieved).
- Hallucination prevention at generation time (prompt-engineering; orthogonal).
- Non-Australian jurisdictions.

---

## Open Questions

1. Is there an authoritative section→act lookup available to Clairo, or would it need to be curated? This is the load-bearing decision for C-02's feasibility. A small curated YAML covering the ~100 sections commonly referenced in tax planning would be sufficient.
2. Should "weak match" citations (body-text mention but no metadata equality) render differently in the UI, or be treated identically to full `verified`? Probably render differently, but the UI work is separate.
3. For C-04, is "clear scenarios on low confidence" the right behaviour, or is "keep scenarios, warn prominently" better? Current inconsistency suggests product hasn't decided. Needs a pass.

---

## Notes

- All file:line references in this brief were verified against the branch `059-2-tax-planning-correctness-followup` at commit `93653f3` (2026-04-18).
- A full technical audit of the verifier lives in the conversation transcript from the 2026-04-18 session — source material if spec work begins.
