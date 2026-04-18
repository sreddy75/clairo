# Feature Specification: Citation Substantive Validation

**Feature Branch**: `061-citation-validation`
**Created**: 2026-04-18
**Status**: Draft
**Input**: Brief `specs/briefs/2026-04-18-citation-substantive-validation.md` (post-059-2 UAT findings; supersedes the original "Story 6" from HANDOFF.md).

---

## Origin & Problem

Spec 059-2 landed an arithmetically correct multi-agent tax planning pipeline (UAT verified at $24,375 Total Tax Saving, reviewer-confirmed "arithmetically consistent"). With the double-counting bug gone, the reviewer's quality findings are now dominated by a different class of defect: **citation quality**. The same UAT run produced two concrete flags that the current citation verifier does not catch:

1. *"TR 2012/8 cannot be confirmed as a real ATO ruling on prepayments and may be fabricated."*
2. *"The prepaid expenditure provisions are incorrectly attributed to ITAA 1997 when s 82KZM and s 82KZMD are ITAA 1936 provisions."*

The first flag points to a structural weakness in how the verifier decides "this ruling is real": it accepts any surface-level substring appearance of the ruling identifier in any retrieved knowledge chunk, regardless of whether that chunk is *about* that ruling. A hallucinated ruling ID that happens to appear as a cross-reference somewhere in the knowledge base passes verification and renders as "verified" on the accountant brief.

The second flag points to a class of error the verifier has no ability to detect at all: the LLM gets the section number right but attributes it to the wrong Act (ITAA 1997 vs ITAA 1936). The current extraction regex drops the act-year suffix before comparison, and no metadata field on either the citation or the chunk records which Act a section belongs to. Wrong-act citations verify as happily as correct ones — this is a professional-indemnity (PI) exposure.

Both defects are **quality-of-citation** problems, not arithmetic. The arithmetic fix from 059-2 was necessary but not sufficient: an accountant reading figures out loud to a client is exposed if the supporting citation misattributes the legislation, regardless of how correct the numbers are. PI insurance cares about both dimensions.

The fix approach mirrors 059-2's principle of "code is law": the verifier must enforce structural guarantees (topical relevance, act-year correctness) rather than relying on surface-level string matches that the LLM can bypass with plausible-looking but wrong output.

### What is already fixed and explicitly out of scope

- The original `semantic=0` dict-key-typo bug (HANDOFF.md's original "Story 6"). Resolved under Spec 059 — see the fix comment at `backend/app/modules/tax_planning/service.py:1457-1459` and the regression test at `backend/tests/e2e/tax_planning/test_citation_regression_bank.py:97`. This spec MUST NOT reintroduce that bug and the regression test MUST continue to pass.

---

## Clarifications

### Session 2026-04-18

- **Q1 (section→act mapping source)** → **A: hand-curated YAML** of the top ~100 Australian tax-law sections seen in production citation traffic, domain-expert reviewable, extendable via pull request.
- **Q2 (sub-threshold confidence-gate parity rule)** → **C: hybrid** — preserve LLM content (streaming-style) but always clear persisted scenarios (non-streaming-style); warning banner remains. Most consistent with "AI suggests, human approves" (constitution XI).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Accountant can trust the "verified" badge on a ruling citation (Priority: P1)

An accountant reads a generated tax planning document that cites an Australian Taxation Office ruling (e.g., "TR 2012/8"). The document shows the citation as "verified." The accountant trusts that badge because the platform has structurally confirmed the ruling is real and topical — not merely that the ruling's identifier string appears somewhere in the retrieved reference material. A plausible-looking but hallucinated ruling ID cannot achieve the "verified" badge.

**Why this priority**: Professional-liability risk is asymmetric. A reviewer flagging a suspicious citation is a recoverable situation — the accountant checks manually and proceeds. A "verified" badge on a hallucinated ruling is a silent failure: the accountant never checks, reads it out loud to the client, and discovers the error only after it has been relied on. This is the highest-severity quality defect the platform currently ships.

**Independent Test**: Construct a test harness where an LLM response cites a ruling identifier (e.g., "TR 9999/99") that does not appear as the primary metadata (`ruling_number` field) of any retrieved chunk, but does appear as prose cross-reference inside an unrelated chunk's body text. The verifier MUST flag this citation as `verified=False`. A citation whose identifier matches a retrieved chunk's `ruling_number` metadata exactly MUST still verify.

**Acceptance Scenarios**:

1. **Given** a citation of "TR 2024/1" and a retrieved chunk whose `ruling_number` metadata is exactly "TR 2024/1", **When** the verifier runs, **Then** the citation is marked `verified=True`.
2. **Given** a citation of "TR 9999/99" and no retrieved chunk with matching `ruling_number` metadata (regardless of whether any chunk's prose contains the string), **When** the verifier runs, **Then** the citation is marked `verified=False`.
3. **Given** a citation of "TR 2024/1" matched by body text only (the chunk's `ruling_number` is different but the prose mentions "TR 2024/1" in passing), **When** the verifier runs, **Then** the citation is distinguishable from a metadata-verified citation — a downstream consumer can tell a "strong" match from a "weak" match.

---

### User Story 2 — Accountant is warned when the LLM misattributes a section to the wrong Act (Priority: P1)

When the AI generates a document that cites a tax-law section (e.g., "s 82KZM"), the accountant sees a clear warning if the LLM has attributed the section to the wrong Act (e.g., claiming s 82KZM belongs to ITAA 1997 when in fact it belongs to ITAA 1936). The accountant can fix the attribution before the document reaches the client.

**Why this priority**: Wrong-act attributions are a common PI-exposure class in Australian tax-agent professional-indemnity claims. A section correctly quoted but attributed to the wrong Act confuses a court and undermines the agent's advice credibility. The platform currently cannot detect this class of error at all.

**Independent Test**: The verifier, given a citation of the form "s 82KZM ITAA 1997", consults an authoritative section→act mapping and flags `verified=False` with reason `wrong_act_year`. The same section correctly cited as "s 82KZM ITAA 1936" verifies normally.

**Acceptance Scenarios**:

1. **Given** a citation "s 82KZM ITAA 1997", **When** the verifier runs and the authoritative mapping records this section as belonging to ITAA 1936, **Then** the citation is marked `verified=False` and carries a machine-readable reason identifying the mis-attribution.
2. **Given** a citation "s 82KZM ITAA 1936" (same section, correctly attributed), **When** the verifier runs, **Then** the citation verifies normally.
3. **Given** a citation whose section is not present in the authoritative mapping, **When** the verifier runs, **Then** the citation is not penalised for the absence of mapping data (unknown does not equal wrong) — it falls back to the existing metadata/body-text match logic without any act-year check.

---

### User Story 3 — Engineer has unit-test safety net before changing verifier behaviour (Priority: P2)

Before any behavioural change to the citation verifier lands, a comprehensive unit-test safety net exists for the module. A developer editing extraction, matching, or scoring logic receives immediate pass/fail feedback on every branch of the verifier — including the paths that the existing e2e fixture test does not exercise.

**Why this priority**: The verifier currently has one single e2e fixture test. Every branch in the extraction regex, the metadata-match path, the body-text-match path, and the confidence aggregation is otherwise untested. A change to any of these branches today is high-risk — the test suite cannot tell the developer whether they've broken something subtle. This story is a **prerequisite** for Stories 1 and 2 landing safely; it does not deliver user-visible value on its own.

**Independent Test**: A unit-test suite exists at the appropriate location in the test tree, covers every extraction pattern (numbered, section, ruling) and every match path (metadata hit, body-text hit, miss), runs in under one second total, and fails cleanly on any introduced regression in those branches.

**Acceptance Scenarios**:

1. **Given** a developer changes the extraction regex or matching logic, **When** they run the unit-test suite, **Then** the tests either pass (behaviour preserved) or fail with diagnostics precise enough to identify which code path regressed.
2. **Given** the CI pipeline, **When** a PR modifies the verifier, **Then** the unit-test suite runs, and the PR cannot merge if any test fails.

---

### User Story 4 — Streaming and non-streaming chat modes handle low-confidence responses identically (Priority: P2)

An accountant uses the tax planning chat — either in the "ask and wait for the whole answer" mode or the "watch it type" streaming mode. When the platform's confidence in a response is below threshold (retrieved chunks don't match the question well, or verification rate is low), both modes produce the same user-visible outcome. Today they diverge silently, and the accountant gets different treatment depending on which mode the UI happened to invoke.

**Why this priority**: Silent divergences are discoverable-only-by-accident and erode trust. This is a quiet UX bug that has not been flagged in UAT but is observable in the code. Fixing it is small and decouples the streaming refactor surface from future changes to the confidence gate.

**Independent Test**: For an identical request that triggers the sub-threshold confidence gate, both chat modes produce identical observable outcomes — same status label, same scenario persistence behaviour, same user-facing content.

**Acceptance Scenarios**:

1. **Given** a chat request whose computed confidence is below the low-confidence threshold and retrieved chunks are non-empty, **When** the request is handled via the streaming code path vs the non-streaming code path, **Then** both paths produce the same status label, the same persisted scenarios (either both cleared or both retained per the product rule), and the same user-visible content.
2. **Given** a chat request whose confidence is above threshold, **When** handled by either path, **Then** the response is returned normally without invoking the low-confidence handling.

---

### Edge Cases

- **Ruling identifier appears verbatim as a superseded cross-reference in an unrelated chunk** — the verifier must treat this as weak match, not strong match, and MUST NOT raise the citation to "verified" status on that basis alone.
- **Section cited with no act suffix** (e.g., just "s82KZM" with no "ITAA 1997" or "ITAA 1936" trailing) — the verifier falls back to section-only matching and does not synthesise an act year. The act-year check is triggered only when the LLM explicitly attributes an act year.
- **Section cited with an act year that is outside the known Australian tax-law corpus** (e.g., "ITAA 2017") — the verifier treats the citation as unknown-act, flags for review, and does not claim either verification or wrong-act-year.
- **Section cited with an obsolete synonym** (e.g., section renumbered after the 1997 rewrite) — out of scope for this spec; handled by retrieval quality or by a separate renumbering-aware matcher, not by this verifier.
- **Numbered citation `[3]` where the matched chunk happens to have a `ruling_number` field populated** — the numbered-citation path remains the source of truth for `matched_by`; the existing observability mislabel (C-05 in the brief) is explicitly out of scope here.
- **Confidence gate fires with zero retrieved chunks** — the low-confidence handling is triggered only when `retrieved_chunks` is non-empty (per current behaviour). Empty chunks are handled upstream by a different path and are out of scope.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001** (Topical relevance — Story 1): For ruling-type citations, the verifier MUST require that the matched chunk's authoritative `ruling_number` metadata field equals the cited ruling identifier exactly (case- and whitespace-insensitive) in order to mark the citation `verified=True` via the "strong match" path.
- **FR-002** (Weak match distinction — Story 1): Body-text mentions of a ruling identifier inside a chunk whose `ruling_number` metadata does NOT match MUST be classified as a weak match, distinguishable from strong matches in the verifier's output. A weak match alone MUST NOT grant the citation `verified=True`; the verifier's output MUST surface the distinction so downstream consumers (UI, audit log, reviewer) can treat weak matches differently.
- **FR-003** (Hallucinated ruling rejection — Story 1): A ruling identifier that appears in no retrieved chunk's `ruling_number` metadata MUST be marked `verified=False` regardless of how many chunks' body text happens to contain the identifier string.
- **FR-004** (Act-year extraction — Story 2): The section-citation extractor MUST capture the act-year suffix ("ITAA 1997", "ITAA 1936", or any other explicit act attribution) as a structured field on the extracted citation, in addition to the existing section-number capture.
- **FR-005** (Act-year validation — Story 2): When a section citation carries an explicit act-year attribution AND the authoritative section→act mapping contains an entry for that section, the verifier MUST compare them. If they disagree, the citation MUST be marked `verified=False` with a machine-readable reason identifying the mis-attribution.
- **FR-006** (Act-year leniency — Story 2): When a section citation carries no act-year attribution, or when the authoritative mapping has no entry for the cited section, the verifier MUST NOT penalise the citation on act-year grounds. Unknown does not equal wrong.
- **FR-007** (Authoritative mapping — Story 2): The platform MUST maintain an authoritative mapping from Australian tax-law section identifiers to their owning Act. The mapping MUST cover at minimum the sections most commonly cited in tax planning (target: the top 100 sections seen in production citation traffic over the preceding 12 months, or a curated list of equivalent scope).
- **FR-008** (Unit-test coverage — Story 3): A unit-test suite for the citation verifier MUST exist, covering every extraction pattern branch (numbered, section, ruling), every match path (metadata strong, body-text weak, miss), and the new act-year branches. Minimum 8 tests. Tests MUST run in under 1 second total.
- **FR-009** (TDD for Stories 1 and 2): Story 3's unit-test suite MUST land before any behavioural change for Story 1 or Story 2 reaches the main code path. The suite MUST include tests that would fail against the pre-change behaviour and pass against the post-change behaviour for every FR-001..FR-007 guarantee.
- **FR-010** (Streaming/non-streaming parity — Story 4): The sub-threshold confidence-gate handling MUST be identical between the streaming and non-streaming chat paths. The product rule for sub-threshold handling (content replacement, scenario clearing, status label) MUST be a single specification shared by both paths; the code MAY share a helper or MAY duplicate the logic, but the observable behaviour MUST match.
- **FR-011** (Regression preservation): The `semantic=0` fix from Spec 059 MUST continue to pass its regression test (`backend/tests/e2e/tax_planning/test_citation_regression_bank.py`). No change in this spec is permitted to break that test.
- **FR-012** (Observability): When the verifier flags a citation as `verified=False` or as a weak match, its output MUST carry a machine-readable reason code (e.g., `wrong_act_year`, `unknown_ruling`, `weak_match_body_only`) distinguishable from the legacy `unverified` catch-all. Downstream audit logs and UI badges MUST be able to render the reason without additional parsing.

### Non-Functional Requirements

- **NFR-001**: The verifier's per-citation latency impact MUST NOT exceed 10ms for the strong-match path and MUST NOT exceed 20ms when the authoritative mapping is consulted. (No mandated framework for how the mapping is queried — just the budget.)
- **NFR-002**: No database schema changes.
- **NFR-003**: No frontend changes required for this spec. UI may render the new reason codes opportunistically in a later spec.
- **NFR-004**: No changes to the tax planning multi-agent pipeline (modeller, scanner, advisor, reviewer, profiler). The verifier is a dependency of the chat and advisor flows but is itself a knowledge-module concern.
- **NFR-005**: The authoritative section→act mapping MUST live in a form that a domain expert (accountant / tax lawyer) can review and amend without needing to run code — plain text, human-readable, reviewable in a pull request.

### Key Entities

- **Citation (extracted)**: A structured representation of one citation found in an LLM response. Carries `type` (numbered, section, ruling), the raw value, and — new in this spec — the captured act-year suffix when present. Emitted by the extractor, consumed by the verifier.
- **Chunk (retrieved)**: Existing entity from the retrieval layer. Carries `ruling_number`, `section_ref`, `title`, body text, and `relevance_score`. Unchanged in shape by this spec; the verifier's new logic reads existing fields only.
- **Section-to-Act mapping (new)**: An authoritative lookup from section identifier to owning Act. Each entry records at minimum the section key and the act identifier. Reviewable by domain experts; loaded once at verifier initialisation.
- **Citation verification result**: Existing entity emitted per citation. Extended in this spec to carry (a) strong-vs-weak match distinction, (b) machine-readable reason code when `verified=False`. Existing consumers (audit log, UI, reviewer) must either ignore the new fields or surface them.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: No.
- [x] **Data Access Events**: No — reads existing retrieval output only.
- [x] **Data Modification Events**: New reason codes added to the existing `tax_planning.citation.verification_outcome` audit event metadata (already logged today via `service.py:1489-1492` and `:1786-1789`). No new event types.
- [x] **Integration Events**: No external integration changes.
- [x] **Compliance Events**: Indirectly positive — improves the citation-verification outcome audit trail that tax agents may be asked to produce under TPB review.

### Audit Implementation Requirements

The existing audit event `tax_planning.citation.verification_outcome` is extended with two new metadata fields:

| Event Type | Trigger | Data Captured (new) | Retention | Sensitive Data |
|------------|---------|---------------------|-----------|----------------|
| `tax_planning.citation.verification_outcome` | On every citation verification pass | Per-citation: `match_strength` (strong/weak/none), `reason_code` (when verified=False). Aggregate unchanged. | 7 years (no change) | None |

### Compliance Considerations

- **ATO Requirements**: Not directly affected. This spec strengthens the platform's ability to detect incorrect Act attributions, which is a professional-judgement concern the platform does not make on behalf of the accountant.
- **TPB (Tax Practitioners Board)**: A registered tax agent is expected to verify the legal citations they provide to clients. This spec strengthens the platform's support for that obligation; it does NOT fulfil it on the agent's behalf. Existing disclaimers ("AI-assisted decision support; does not constitute advice") remain correct and unchanged.
- **Data Retention**: No change.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Across 50 consecutive live UAT analyses run after this spec lands, zero citations marked `verified=True` by the platform are traceable (on manual expert review) to a ruling identifier that is not the subject of any retrieved chunk.
- **SC-002**: On a curated regression fixture of 20 known-wrong-act citations (e.g., "s 82KZM ITAA 1997" where the section belongs to ITAA 1936), 100% are flagged `verified=False` with reason `wrong_act_year`. On a paired fixture of 20 correctly-attributed citations, 100% continue to verify normally. (Fixture curated during implementation; no fewer than 20 in each set.)
- **SC-003**: The unit-test suite for the citation verifier contains at least 8 tests, runs in under 1 second total, and achieves line coverage of the verifier module of at least 85%.
- **SC-004**: Zero observable behavioural divergences between streaming and non-streaming chat paths for sub-threshold confidence handling, across an automated test fixture exercising both paths on the same inputs.
- **SC-005**: The pre-existing `test_citation_regression_bank.py` e2e test continues to pass unchanged on every post-spec build.
- **SC-006**: The authoritative section→act mapping covers at minimum 100 distinct Australian tax-law sections, reviewed by a domain expert, and stored in a form a non-developer can amend via a pull request.

---

## Dependencies & Assumptions

**Dependencies**:

- The existing citation verifier module must remain in place as a starting point — this spec extends it, does not replace it.
- Retrieval output (`relevance_score`-bearing chunks with `ruling_number`, `section_ref`, `title`, body text) is a stable upstream contract. Any change to that contract is out of scope and handled upstream.

**Assumptions**:

- The LLM's citation-emission behaviour is noisy but bounded: citations follow recognisable Australian tax-law patterns (TR YYYY/N for rulings, sNNNN[A-Z]* for sections, numbered `[N]` for inline references). A citation the extractor cannot recognise falls through unverified today and continues to do so under this spec.
- The authoritative section→act mapping is feasible to curate by a domain expert for the sections in production traffic. If this assumption fails (see Clarification Q1), Story 2 falls back to a narrower scope.
- The current 0.5 confidence-gate threshold is correct. This spec does not tune that threshold; it only requires that both chat paths obey the same threshold.

---

## Out of Scope

- The `semantic=0` dict-key-typo bug (fixed in Spec 059).
- Citation formatting in the accountant brief PDF (visual / presentation concern).
- `_infer_matched_by` attribution correctness for numbered citations (C-05 in the brief — observability only).
- RAG retrieval quality / ranking of retrieved chunks.
- Hallucination prevention at LLM generation time (prompt engineering — orthogonal).
- Non-Australian jurisdictions or non-tax domains.
- Section renumbering / obsolete-synonym handling.
- UI changes to render the new reason codes (may be picked up in a later spec).
- Changes to the tax planning multi-agent pipeline (modeller, scanner, advisor, reviewer, profiler).

---

## Clarifications Resolved

Both load-bearing decisions are answered in the **Clarifications** section at the top of this document. For reference:

- **Q1 → A**: hand-curated YAML, ~100 sections initially, PR-extensible. FR-007 interpretation: the mapping file is source-controlled, lives under a knowledge-module data path reviewable by domain experts, and grows organically as new sections appear in production traffic.
- **Q2 → C**: hybrid — preserve content + clear scenarios + warning banner. FR-010 interpretation: both chat paths (a) leave the LLM's text response visible, (b) do not persist any scenarios extracted from a sub-threshold response, (c) surface a low-confidence status/banner the UI renders identically regardless of transport. The canned "decline" text used today in the non-streaming path is replaced by the actual response prefixed by the banner.

*Specification ready for `/speckit.plan`.*
