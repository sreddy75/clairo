# Feature Specification: Tax Strategies Knowledge Base — Phase 1 Infrastructure

**Feature Branch**: `060-tax-strategies-kb`
**Created**: 2026-04-18
**Status**: Draft
**Input**: Tax Strategies Knowledge Base Phase 1 Infrastructure — build the ingestion pipeline, storage model, retrieval integration, citation plumbing, and admin surfaces needed to hold a Clairo-owned, reviewer-approved library of Australian tax planning strategies that the tax planning AI can cite verifiably. Paired brief `specs/briefs/2026-04-18-tax-strategies-knowledge-base.md`; full architecture `docs/tax planning/tax-strategies-architecture.md`.

---

## Context

Clairo's tax planning AI currently suggests strategies drawn from the language model's general training data. Those suggestions carry no traceable source, so Clairo's existing citation verifier cannot confirm them — and in Unni's first live alpha session they produced "Sources could not be verified" badges on every strategy claim. There is no grounded corpus for the AI to cite.

This feature builds the infrastructure that will hold a Clairo-owned, reviewer-approved library of ~415 Australian tax planning strategies, organised across 8 categories, each traceable to ATO primary sources. Phase 1 is the plumbing only — tables, pipeline, admin surfaces, retrieval wiring, citation handling — with enough end-to-end function that one strategy can be moved from stub to published and cited correctly in the tax planning chat. Authoring and reviewing of the 415 strategies themselves is out of scope here; that is Phase 2 onward.

The governing design constraint: **vectors are seeded once in production and shared across all environments**. The parent strategy records held in the relational store may be duplicated per environment, but the vector namespace is the single source of truth — re-embedding per environment is forbidden (cost, drift, and review signature integrity).

---

## Clarifications

### Session 2026-04-18

- Q: What inline markup form should the AI emit for strategy citations, so the CitationVerifier, LLM system prompt, and frontend tokenizer all agree? → A: `[CLR-XXX: Name]` — square-bracket enclosed, colon-separated identifier + human-readable name.
- Q: What threshold flips a citation from verified to partially verified when the identifier matches but the cited name has drifted? → A: Normalized Levenshtein distance ≥ 0.30 between cited name and stored name (both lower-cased, whitespace-collapsed).
- Q: How does the publish code determine whether the current environment is authorised to write to the shared vector store? → A: Dedicated env flag `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default false); set true only in the production deployment; publish refuses vector write and fails the job when unset.
- Q: In Phase 1, with the admin detail view otherwise read-only, how does a super-admin drive a strategy through submit-for-review, approve, and publish? → A: Interactive action buttons (submit-for-review, approve, publish, reject) are in scope for Phase 1 even though field editing is deferred to Phase 2; the approve action captures reviewer identity for FR-006.
- Q: What format does the bulk seed action consume for the 415-strategy catalogue? → A: A committed in-repo CSV fixture at `backend/app/modules/tax_strategies/data/strategy_seed.csv` with columns `strategy_id,name,categories,source_ref` (categories pipe-separated for multi-tag; `source_ref` is internal-only per FR-008).

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — One strategy end-to-end (Priority: P1)

A platform super-admin picks a stub strategy in the admin interface (e.g. "Concessional super contributions"), moves it through the authoring lifecycle — research, draft, enrich, submit for review, approve, publish — and confirms that an accountant asking a relevant question in the tax planning chat sees a clickable citation chip referencing that strategy, verified against the stored record.

**Why this priority**: This is the Phase 1 exit criterion. It proves every link of the chain is wired correctly: the data model holds the strategy, the pipeline moves it through states, chunking and embedding produce retrievable vectors, retrieval returns the strategy for a relevant query, the AI cites it using the agreed markup, the citation verifier confirms the match, and the frontend renders it as a clickable chip. Without this end-to-end path, no Phase 2 content work can begin.

**Independent Test**: A super-admin runs the flow manually in a non-production environment on a single fixture strategy, then poses a question in the tax planning chat that should surface that strategy. The chat response contains a green citation chip referencing the strategy by its Clairo identifier; clicking the chip opens a panel showing the full strategy content.

**Acceptance Scenarios**:

1. **Given** a stub strategy exists in the admin list, **When** the super-admin advances it through research → draft → enrich → approve → publish, **Then** the strategy becomes retrievable by semantic and keyword search.
2. **Given** a published strategy covering a topic (e.g. concessional super), **When** an accountant asks a relevant question in tax planning chat, **Then** the response includes a citation chip referencing the strategy by its Clairo identifier, rendering as verified (green).
3. **Given** a response contains a citation for a strategy that was not in the retrieved set, **When** the citation verifier evaluates the response, **Then** the chip renders as unverified (red) and the message-level citation badge reflects the failure.
4. **Given** the published strategy, **When** the super-admin searches for it in the admin search-test interface using either its name or a topic keyword, **Then** the strategy appears in the top results with category and section labels visible.

---

### User Story 2 — Citation trust visible to accountants (Priority: P1)

An accountant using the tax planning chat receives a response that cites one or more strategies. Each citation renders inline as a clickable chip whose colour reflects whether the citation is verified against a real strategy record (green = exact match, amber = partial match with minor name drift, red = no matching strategy). Clicking a chip opens a panel with the full strategy content, including implementation steps and ATO source references.

**Why this priority**: This is the user-visible payoff of the whole Phase 1 effort. The infrastructure exists to serve this moment — when the accountant can see, trust, and click through to strategy evidence. Without this working, Phase 1 has no visible value; with this working, Phase 2 content authoring produces compounding trust gains.

**Independent Test**: With one published strategy available, the accountant asks a relevant tax planning question; the response includes at least one citation chip that renders green, is clickable, opens a panel with the full strategy content, and the message-level citation summary reflects the verified state.

**Acceptance Scenarios**:

1. **Given** a response from the tax planning chat containing a strategy citation in the agreed markup, **When** the chat renders, **Then** the citation appears as an inline clickable chip with colour matching verification state.
2. **Given** a verified citation chip, **When** the accountant clicks it, **Then** a panel opens showing the full strategy — implementation steps, explanation, ATO sources, case references.
3. **Given** a response containing citations for one verified strategy and one hallucinated identifier, **When** the citation verifier evaluates the response, **Then** the first chip renders green and the second renders red; the message-level badge reflects partial verification.
4. **Given** no strategies are published yet, **When** the accountant asks a question, **Then** tax planning chat behaviour is unchanged from before this feature — no new chips, no regression on existing compliance-knowledge citations.

---

### User Story 3 — Admin surfaces for strategy governance (Priority: P2)

A super-admin navigates to the knowledge admin area, opens a new Strategies tab, sees the full list of strategy records with their authoring status, filters by status / category / tenant, opens any row to view its full detail (implementation steps, explanation, eligibility metadata, ATO sources, authoring job history), and monitors the pipeline via a kanban-style dashboard showing counts per stage.

**Why this priority**: Governs the ability to operate the authoring pipeline at scale. The reviewer queue — the rate-limiting step for Phase 2 — lives here. Without this surface, the super-admin cannot see what is in flight, what needs review, or what has been published. Read-only in Phase 1 (edit lands in Phase 2 when content authoring begins in earnest).

**Independent Test**: A super-admin opens the admin Strategies tab with 415 stub records present, confirms list pagination and filtering work, opens a detail view for any strategy and sees all fields rendered read-only, and opens the pipeline dashboard to see accurate status counts.

**Acceptance Scenarios**:

1. **Given** 415 stub strategies have been seeded, **When** the super-admin opens the Strategies tab, **Then** a paginated list renders with columns for identifier, name, categories, status, last reviewed, reviewer, and version.
2. **Given** the list view, **When** the super-admin applies a status filter (e.g. "in review"), **Then** only strategies in that status are shown.
3. **Given** a strategy in any status, **When** the super-admin opens its detail view, **Then** all fields (implementation steps, explanation, eligibility metadata, ATO sources, case refs, authoring job history, version history) render correctly in read-only form.
4. **Given** the pipeline dashboard, **When** strategies are in mixed statuses, **Then** the kanban columns show accurate counts per stage and flag the in-review queue prominently.

---

### User Story 4 — Seeding the catalogue (Priority: P2)

A super-admin runs a one-time seeding action that imports the 415-strategy catalogue as stub records, each carrying a Clairo-owned identifier, name, category assignment, and an internal-only reference back to the source blueprint. After seeding, the admin sees all 415 records in "stub" status awaiting authoring.

**Why this priority**: Prerequisite for Phase 2 content work. Without the stubs in place, there is nothing for Phase 2 authoring to drive through the pipeline. The action is idempotent — re-running it does not create duplicates. Runnable in any environment but conceptually a one-time production operation.

**Independent Test**: A super-admin runs the seed action in a fresh environment; afterwards the strategy list shows 415 records, all in stub status, each with a unique Clairo identifier and category assignment. Re-running the action produces no new records.

**Acceptance Scenarios**:

1. **Given** an empty strategies catalogue, **When** the super-admin runs the seed action, **Then** 415 strategy stub records are created with Clairo identifiers assigned sequentially.
2. **Given** 415 stub records exist, **When** the super-admin re-runs the seed action, **Then** no duplicate records are created and existing records are not overwritten.
3. **Given** the seeded catalogue, **When** the super-admin filters by category, **Then** strategies fall into the expected 8 categories matching the blueprint taxonomy.

---

### Edge Cases

- **Seeding conflict**: re-running the bulk seed action must not create duplicates; identifier collisions must be detected and refused.
- **Namespace already initialised**: the new strategies namespace must register cleanly whether or not other knowledge namespaces already exist.
- **Vector duplication across environments**: the publish action must not re-embed or re-upsert a vector for a strategy already published in the shared vector store; lower environments must read from the shared store without writing to it.
- **Partial publish failure**: if the embed step succeeds but the chunk-record write fails (or vice versa), the strategy must remain in "approved" status with a failed job row — never in an inconsistent "half-published" state.
- **Superseded strategies**: a strategy whose replacement has published must not appear in retrieval results, even if its vector still exists in the shared store.
- **Retrieval with no published strategies**: the tax planning retrieval path must degrade gracefully to its current behaviour when the strategies namespace is empty — no exceptions, no empty-state badges, no performance regression.
- **Citation drift**: a response containing a citation whose identifier matches but whose name has drifted (e.g. the AI paraphrased the name) must render as partially verified, not as a failure.
- **Structured filter over-restriction**: if the eligibility pre-filter would exclude all candidates for a given client context, retrieval must fall back to unfiltered semantic search rather than returning empty.
- **Long strategy sections**: strategies whose explanation or implementation text exceeds the chunk budget must split cleanly at paragraph boundaries, with every split piece carrying the same context header.
- **Hallucinated identifier**: a response citing an identifier not in the retrieved set (e.g. `CLR-999`) must render red, surface in the message-level badge, and not break the response render.

---

## Requirements *(mandatory)*

### Functional Requirements

#### Storage & identity

- **FR-001**: The system MUST persist each strategy as an authoritative parent record carrying a Clairo-owned identifier (format `CLR-###`), name, category tags, implementation text, explanation text, eligibility metadata, ATO source references, case references, version, status, review metadata, applicable financial-year window, and an optional internal-only reference to the source blueprint.
- **FR-002**: The system MUST enforce uniqueness of Clairo identifiers across all strategies.
- **FR-003**: The system MUST support multi-tag categorisation across the 8 blueprint categories (Business, Recommendations, Employees, ATO obligations, Rental properties, Investors & retirees, Business structures, SMSF); a single strategy may belong to multiple categories.
- **FR-004**: The system MUST scope every strategy to either a platform baseline or a specific tenant overlay, so that future private overlays do not leak across tenants.
- **FR-005**: The system MUST track lifecycle status for each strategy across: stub, researching, drafted, enriched, in_review, approved, published, superseded, archived.
- **FR-006**: The system MUST record the identity of the reviewer who approved a strategy for publication and the timestamp of approval.
- **FR-007**: The system MUST support versioning: substantive changes produce a new version with a reference to the prior version; minor changes update in place; only the current version is discoverable in retrieval.
- **FR-008**: The system MUST NOT surface the internal-only source reference to any end user (accountant, super-admin presentation, API response to client portals) — it is carried only as internal metadata.

#### Authoring pipeline

- **FR-009**: The system MUST provide an authoring pipeline with four background stages — research, draft, enrich, publish — each independently invocable by a super-admin on a given strategy.
- **FR-010**: The system MUST record every pipeline stage execution as a job with status (pending, running, succeeded, failed), timestamps, input payload, output payload, and error detail on failure.
- **FR-011**: The system MUST mark a strategy as inconsistent (status remains "approved" with a failed publish job) rather than "published" if any step of the publish sequence fails partway through; retries MUST be safe and idempotent.
- **FR-012**: The system MUST provide a bulk seeding action that creates stub records for the full 415-strategy catalogue from a committed in-repo CSV fixture at `backend/app/modules/tax_strategies/data/strategy_seed.csv` (columns: `strategy_id`, `name`, `categories` as pipe-separated list, `source_ref`), assigning Clairo identifiers as provided in the fixture and populating name, categories, and the internal-only source reference; the action MUST be idempotent and refuse to create duplicates on re-run.

#### Retrieval & citation

- **FR-013**: The system MUST chunk each published strategy into exactly two retrievable pieces — one for the implementation text, one for the explanation text — with any section exceeding the chunk size splitting at paragraph boundaries such that every resulting piece carries the same identifying context header.
- **FR-014**: The system MUST prepend to every chunk a context header containing the Clairo identifier, strategy name, and primary category, and append to every chunk a keyword tail derived from the strategy's alias/shorthand list.
- **FR-015**: The system MUST index every chunk in both the semantic (vector) store and the lexical (keyword) index used for hybrid retrieval.
- **FR-016**: The system MUST surface strategies to retrieval callers by allowing opt-in inclusion of the strategies namespace alongside existing knowledge namespaces; default retrieval behaviour for existing callers MUST remain unchanged.
- **FR-017**: The system MUST support structured pre-filtering of candidate strategies by client eligibility axes — entity type, income band, turnover band, age, industry — before semantic ranking. If the filter would return no candidates, retrieval MUST fall back to unfiltered semantic search.
- **FR-018**: Retrieval MUST deduplicate candidates by parent strategy (a single strategy appearing via both its implementation and explanation chunks counts once) and return reranked results scored against the full parent content.
- **FR-019**: Retrieval MUST exclude strategies in superseded or archived status.
- **FR-020**: The system MUST recognise strategy citations in generated responses using the inline markup `[CLR-XXX: Name]` (square brackets, Clairo identifier, colon, strategy name), and classify each citation as verified (exact identifier match against retrieved set), partially verified (identifier match but normalized Levenshtein distance ≥ 0.30 between cited name and stored name, both lower-cased and whitespace-collapsed), or unverified (no matching retrieved strategy). This is the single canonical form the AI emits, the CitationVerifier parses, and the frontend tokenizer matches.
- **FR-021**: The message-level citation summary MUST reflect the combined verification state of all strategy citations in the response, alongside existing section-reference and ruling-number verification counts.
- **FR-022**: The tax planning chat UI MUST render each strategy citation as an inline clickable chip whose colour reflects verification state, and whose activation opens a detail panel showing the full strategy content and source references without requiring the full content to be embedded in the chat message itself.

#### Admin surfaces

- **FR-023**: The system MUST provide a new Strategies tab in the knowledge admin area, restricted to super-admin users, presenting a paginated list view with filters by status, category, and tenant scope.
- **FR-024**: The system MUST provide a read-only detail view for each strategy showing all persisted fields, version history, and authoring job history.
- **FR-025**: The system MUST provide a pipeline dashboard view showing counts per authoring stage, highlighting the in-review queue.
- **FR-026**: The system MUST surface the new strategies namespace in the existing admin collections view and search-test view automatically once the namespace is initialised, without requiring bespoke wiring in those views.

#### Environment & cost constraints

- **FR-027**: The system MUST treat the strategies vector store as a single shared resource across all environments. The publish action MUST NOT re-embed or re-upsert a vector for a strategy whose identifier and version already exist in the shared vector store.
- **FR-028**: The publish action MUST be gated on a dedicated environment flag `TAX_STRATEGIES_VECTOR_WRITE_ENABLED` (default false). Vector-store writes MUST proceed only when the flag is true; the flag is set true only in the production deployment. Parent-record and chunk-record writes to the relational store may occur in any environment. If a publish job runs in an environment where the flag is false, the job MUST refuse the vector write and mark itself failed with a clear error (leaving the strategy in `approved` status per FR-011), rather than silently skipping.
- **FR-029**: Non-production environments MUST be able to read from the shared vector store for retrieval without requiring local vector writes.
- **FR-030**: A local / developer test path MUST exist that exercises the full pipeline against a small fixture set (3–5 strategies) without touching the production catalogue.

### Key Entities

- **Tax Strategy**: The authoritative parent record for a single tax planning strategy. Carries identity (Clairo identifier, optional internal source reference), tenancy scope (platform vs specific tenant), presentation content (name, categories, implementation text, explanation text), eligibility metadata (entity types, income band, turnover band, age band, industry triggers, financial-impact types, keywords), source attribution (ATO source references, case references), lifecycle state (status, version, supersession pointer, applicable financial-year window), and governance metadata (reviewer identity, last-reviewed timestamp). Relates to many chunk records and many authoring job records.

- **Strategy Chunk**: A retrievable sub-unit of a strategy (implementation or explanation). Carries identity back to the parent strategy, a section label, the context header prepended for retrieval, and the chunk body stored alongside existing knowledge chunks. Replicated in the vector store and the keyword index.

- **Authoring Job**: A single execution of one pipeline stage (research, draft, enrich, publish) for one strategy. Carries stage, status, timestamps, input and output payloads, error detail if failed, and the identity of whoever triggered it. Used to populate the admin pipeline dashboard and the per-strategy job history.

- **Citation (in responses)**: An inline reference in a generated tax planning response pointing to a strategy by its Clairo identifier and name. Not persisted as a separate entity — derived from response text by the citation extractor and resolved against the retrieved-strategies set served to the AI for that response.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No change. Admin access uses existing super-admin gating.
- [ ] **Data Access Events**: No sensitive client data read by this feature; strategies are platform content, not client financial data.
- [x] **Data Modification Events**: Strategy lifecycle transitions (approval, publication, supersession) are high-consequence governance events and MUST be audited.
- [ ] **Integration Events**: No Xero / MYOB / ATO integration in Phase 1.
- [x] **Compliance Events**: Strategy publication directly affects the AI's grounded citation corpus; every publish and every approval MUST be traceable for reviewer accountability.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `tax_strategy.created` | Stub creation (including bulk seed) | strategy_id, name, categories, tenant scope, triggered_by | 7 years | None |
| `tax_strategy.status_changed` | Any lifecycle transition | strategy_id, from_status, to_status, version, triggered_by | 7 years | None |
| `tax_strategy.approved` | Reviewer approves for publication | strategy_id, version, reviewer identity, timestamp | 7 years | None |
| `tax_strategy.published` | Publish action succeeds | strategy_id, version, chunk count, vector-store environment | 7 years | None |
| `tax_strategy.superseded` | Replacement version published | old strategy_id, new strategy_id, version numbers | 7 years | None |
| `tax_strategy.seed_executed` | Bulk seed action run | count of stubs created, count skipped (idempotent), triggered_by | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: No direct ATO compliance surface in this feature. However, every published strategy MUST carry at least one ATO source reference (enforced in Phase 2 content authoring). The audit trail on publications gives the reviewer a defensible record of what content entered the corpus and when.
- **Data Retention**: Standard 7 years aligns with the existing platform policy.
- **Access Logging**: Super-admin access to the Strategies tab and pipeline dashboard follows existing admin-audit logging — no separate access log is required.
- **Reviewer accountability**: The reviewer MUST be identifiable in the audit trail for every approval event. Combined with version history, this gives a per-strategy chain of custody.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: A super-admin can move a single strategy end-to-end from stub to cited-in-chat within 30 minutes of manual work, across all pipeline stages, without hitting environmental blockers or undocumented steps.
- **SC-002**: After Phase 1 completion, the strategies catalogue contains 415 stub records, each with a unique Clairo identifier and correct category assignment matching the blueprint taxonomy.
- **SC-003**: At least one strategy is fully published end-to-end in a non-production environment and renders as a verified citation chip in tax planning chat on a relevant query.
- **SC-004**: Existing retrieval callers (client chat, knowledge chat, tax planning, insight engine) behave identically to their pre-Phase-1 behaviour when no strategies are published — zero regressions on existing compliance-knowledge citations, zero exceptions, zero performance delta beyond noise.
- **SC-005**: Vector store contains exactly one set of strategy vectors across all environments combined; re-running the publish action for an already-published strategy-version produces no new vectors.
- **SC-006**: A developer can exercise the full pipeline locally against a fixture of 3–5 strategies without touching production data or writing to the shared vector store.
- **SC-007**: The citation verifier correctly classifies citations in a controlled test: exact identifier match → verified; identifier match with name drift beyond threshold → partially verified; no matching strategy → unverified. All three paths demonstrated with visible UI state in the chat.
- **SC-008**: The admin Strategies tab loads a 415-record list view and allows filtering by status, category, and tenant without perceptible lag on first interaction.
- **SC-009**: Every strategy lifecycle transition (approval, publication, supersession, seed) produces a durable audit event attributable to the actor who triggered it, discoverable via the existing admin audit interface.
- **SC-010**: An accountant in a second live client session (equivalent to the April 2026 alpha) experiences zero "Sources could not be verified" badges on any response that cites a published strategy.

---

## Assumptions

- **Content authoring out of scope**: Actual writing of strategy prose, research of ATO primary sources, and reviewer approval work are Phase 2 deliverables. Phase 1 ships with 415 stubs and at most a handful of fully-authored fixtures used to prove the pipeline.
- **Edit in admin detail view is read-only in Phase 1**: Full *field editing* (markdown editors for implementation/explanation, form controls for eligibility metadata, etc.) ships in Phase 2 when content authoring begins. Phase 1 demonstrates the pipeline using seeded/fixture content. However, *pipeline action controls* — submit-for-review, approve, publish, reject, plus the stage-trigger buttons (research, draft, enrich) — are in scope for Phase 1 so the one-strategy-end-to-end exit criterion can be met and FR-006 reviewer identity can be captured at approval.
- **Tenant overlays deferred**: Per-tenant private strategy overlays are Phase 3. Phase 1 ships with all strategies scoped to the platform baseline; the tenancy field and filter are in place but only one value is exercised.
- **Review is manual and serial in Phase 1**: No batch-approve, no automated review-signal integration. Reviewer opens a strategy, decides, acts.
- **Gold-set construction and retrieval tuning are Phase 2**: Recall / precision thresholds from the architecture validation plan (e.g. recall ≥ 90% @ top-5) are evaluated in Phase 2 against a gold-set built with the reviewer. Phase 1 success is structural, not quantitative-quality.
- **No indicative-dollar figure**: The blueprint includes an indicative dollar value per strategy; Clairo drops this — the tax planning calculation engine produces client-specific numbers. The data model carries no such field.
- **Blueprint is a coverage list, not source content**: The 415-strategy catalogue derived from the source index is used only to confirm coverage completeness and sequence the Clairo identifiers. The source blueprint's prose is NOT ingested, paraphrased, or copied — all strategy text in Phase 2 is authored fresh from ATO primary sources.
- **Existing knowledge module patterns followed**: The new strategies module, the new admin tab, the new chunker class, the new retrieval extensions, and the new citation markup all extend existing patterns in the knowledge module rather than introducing parallel infrastructure.
- **Production is the designated vector source-of-truth environment**: Publish-time vector writes are gated to production; all other environments read from the shared production namespace and may not write to it.

---

## Dependencies

- **Existing knowledge module**: Phase 1 extends the existing vector store, hybrid retrieval, citation verifier, and admin knowledge UI. All four must remain in their current stable state during the build.
- **Existing tax planning retrieval hook**: The tax planning module's single integration point for knowledge retrieval is extended to opt into the new namespace. No other tax planning call sites are affected.
- **Shared vector store access**: Non-production environments require read access to the production vector namespace. Production credentials are scoped accordingly; writes from non-production environments are forbidden by the publish action's environment gate.
- **Blueprint coverage list**: A stable, versioned form of the 415-strategy index (identifier + name + category assignments + internal source reference) is needed to drive the bulk seed action. The list is committed in-repo at `backend/app/modules/tax_strategies/data/strategy_seed.csv` — derived once from the external reference material at `/Users/suren/KR8IT/projects/Personal/Clairo docs/Tax Fitness Strategy/` and thereafter owned by the repo. The external reference is not consulted at seed time.
- **Reviewer arrangement**: Phase 2 depends on the paid reviewer arrangement being in place; Phase 1 does not depend on it. (Phase 1's "approved" action can be exercised by any super-admin for pipeline demonstration purposes.)

---

## Out of Scope

- Authoring prose for any of the 415 strategies beyond fixture demonstrations.
- Editing strategies in the admin detail view.
- Per-tenant private strategy overlays (Phase 3).
- Annual ATO-source-change review tasks (Phase 4).
- Gold-set construction, retrieval quality benchmarks, recall/precision measurement.
- Production execution of the bulk seed (seed logic ships Phase 1; production execution is a Phase 2 kickoff operation).
- Batch approval actions in the admin UI (reviewer approves each strategy individually by design).
- Structured eligibility metadata accuracy review at scale (Phase 2).
- Surfacing strategies in any client-facing portal beyond the existing accountant tax planning chat.
