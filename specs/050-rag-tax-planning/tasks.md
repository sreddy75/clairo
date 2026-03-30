# Tasks: RAG-Grounded Tax Planning

**Input**: Design documents from `/specs/050-rag-tax-planning/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Tests included as final phase per constitution requirement (80% unit, 100% endpoints).

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/050-rag-tax-planning`
  - Verify: You are now on the feature branch
  - _Note: Branch `050-rag-tax-planning` already exists from speckit — switch to it if needed_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration and model changes needed by all user stories

- [x] T001 Create Alembic migration adding `source_chunks_used` (JSONB, nullable) and `citation_verification` (JSONB, nullable) columns to `tax_plan_messages` table in `backend/app/modules/tax_planning/`
  - Run: `cd backend && uv run alembic revision --autogenerate -m "add RAG fields to tax_plan_messages"`
  - Verify: Migration file created, applies cleanly with `uv run alembic upgrade head`

- [x] T002 Update TaxPlanMessage model to add `source_chunks_used` and `citation_verification` JSONB columns in `backend/app/modules/tax_planning/models.py`
  - Both columns: `Column(JSONB, nullable=True)`
  - No default values

- [x] T003 Update message response schema to include `source_chunks_used` and `citation_verification` as optional fields in `backend/app/modules/tax_planning/schemas.py`
  - Add `SourceChunkRef` schema: chunk_id, source_type, title, ruling_number, section_ref, relevance_score
  - Add `CitationVerificationResult` schema: total_citations, verified_count, unverified_count, verification_rate, status
  - Add both as `Optional` fields on the message response schema

**Checkpoint**: Migration applies, model compiles, schema validates

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core RAG wiring that must be complete before user stories can deliver value

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T004 Add `format_reference_material(chunks)` function in `backend/app/modules/tax_planning/prompts.py`
  - Takes a list of retrieved chunks (each with title, source_type, ruling_number, section_ref, text)
  - Formats as numbered references: `[1] {title} ({ruling_number or section_ref})\n{text}\n`
  - Returns empty string if no chunks provided
  - Max 5 chunks, truncate text to 500 tokens each

- [x] T005 Update `TAX_PLANNING_SYSTEM_PROMPT` in `backend/app/modules/tax_planning/prompts.py`
  - Add `{reference_material}` placeholder to the template
  - Add citation instructions block: "When your advice aligns with a reference, cite it inline using [Source: {identifier}]. Include a ## Sources section at the end listing all cited references. If no reference supports a claim, state it is based on general knowledge."
  - When reference_material is empty, include instruction: "No reference material available. Clearly note that advice is based on general knowledge."

- [x] T006 Update `TaxPlanningAgent` to accept `reference_material` parameter in `backend/app/modules/tax_planning/agent.py`
  - Add `reference_material: str | None = None` to `process_message()` and `process_message_streaming()` signatures
  - Pass to `_build_system_prompt()` which injects it into the prompt via the `{reference_material}` placeholder

- [x] T007 Add RAG retrieval logic to `send_chat_message_streaming()` in `backend/app/modules/tax_planning/service.py`
  - Import `KnowledgeService` from `app.modules.knowledge.service`
  - Import `QueryRouter` from `app.modules.knowledge.retrieval.query_router`
  - Before calling the agent:
    a. Classify query via QueryRouter — skip retrieval if conversational (greetings, < 10 chars)
    b. Build metadata filters: `entity_types` contains plan's entity_type, `topic_tags` from query classification
    c. Call `KnowledgeService.search_knowledge()` with query, namespace=`compliance_knowledge`, limit=8
    d. Take top 5 reranked results
    e. Format via `format_reference_material()`
    f. Pass as `reference_material` to agent

- [x] T008 Add citation verification and metadata saving to `send_chat_message_streaming()` in `backend/app/modules/tax_planning/service.py`
  - Import `CitationVerifier` from `app.modules.knowledge.retrieval.citation_verifier`
  - After streaming completes and final content is assembled:
    a. Run `CitationVerifier.verify()` on the response content with the retrieved chunks
    b. Yield a `verification` SSE event with `{total_citations, verified_count, unverified_count, verification_rate, status}`
    c. Save `source_chunks_used` (chunk refs with scores) and `citation_verification` (verification result) on the assistant message record

- [x] T009 Apply the same RAG retrieval logic to the non-streaming `send_chat_message()` method in `backend/app/modules/tax_planning/service.py`
  - Mirror the retrieval, reference material injection, and verification saving from T007/T008
  - Return citation_verification in the response dict

**Checkpoint**: Backend RAG pipeline complete — sending a chat message retrieves knowledge, injects references, and saves verification metadata. No frontend changes yet.

---

## Phase 3: User Story 1 — Accountant Receives Cited Tax Planning Advice (Priority: P1)

**Goal**: Tax planning chat responses include inline citations to ATO sources and a Sources section, with citation verification metadata saved.

**Independent Test**: Ask the tax planning chat a strategy question with a populated knowledge base. Verify response contains `[Source: ...]` citations and a `## Sources` section. Verify `source_chunks_used` and `citation_verification` are saved on the message.

### Implementation for User Story 1

- [x] T010 [US1] Update frontend types to include citation fields in `frontend/src/types/tax-planning.ts`
  - Add `SourceChunkRef` interface: chunk_id, source_type, title, ruling_number, section_ref, relevance_score
  - Add `CitationVerification` interface: total_citations, verified_count, unverified_count, verification_rate, status
  - Add both as optional fields on the message type
  - Add `VerificationStatus` type: `'verified' | 'partially_verified' | 'unverified' | 'no_citations'`

- [x] T011 [P] [US1] Create CitationBadge component in `frontend/src/components/tax-planning/CitationBadge.tsx`
  - Accept `verification: CitationVerification | null` prop
  - Render shadcn `Badge` component:
    - Green `bg-emerald-100 text-emerald-700`: "Sources verified" when rate >= 0.9
    - Amber `bg-amber-100 text-amber-700`: "Some sources unverified" when 0.5 <= rate < 0.9
    - Red `bg-red-100 text-red-700`: "Sources could not be verified" when rate < 0.5
    - Stone `bg-stone-100 text-stone-700`: "General knowledge" when status is `no_citations` or null
  - Use `cn()` from `@/lib/utils` for conditional classes

- [x] T012 [US1] Handle `verification` SSE event in `frontend/src/components/tax-planning/ScenarioChat.tsx`
  - Add `verification` to the SSE event type handling (alongside existing `thinking`, `content`, `scenario`, `done`)
  - Store verification result in message state
  - For historical messages loaded via `listMessages()`, read `citation_verification` from the message object

- [x] T013 [US1] Render CitationBadge below assistant messages in `frontend/src/components/tax-planning/ScenarioChat.tsx`
  - Import and render `CitationBadge` below each assistant message bubble
  - Pass `verification` data from message state or loaded message object
  - Only show for assistant messages (not user messages)

**Checkpoint**: Full end-to-end flow works — chat responses show citations with verification badges. This is the MVP.

---

## Phase 4: User Story 2 — Knowledge Base Populated with Tax Planning Content (Priority: P1)

**Goal**: Knowledge base contains indexed ATO content covering the 12 core tax planning topics, ready for retrieval.

**Independent Test**: Go to Admin → Knowledge Base → Search Test tab. Query "prepaid expenses 12 month rule" and verify results include ATO content chunks with source attribution.

### Implementation for User Story 2

- [x] T014 [US2] Create a seed script or admin configuration guide for ATO topic page sources in `backend/app/modules/tax_planning/knowledge_seed.py`
  - Define ~50 targeted ATO URLs covering the 12 core topics:
    - Instant asset write-off, prepaid expenses, Division 7A, SBE concessions
    - CGT concessions, FBT exemptions, superannuation contributions, loss carry-back
    - Company tax rates (base rate entity), trust distributions/Section 100A, R&D tax incentive, PAYG variations
  - Each entry: URL, title, topic_tags, entity_types metadata
  - Function to create KnowledgeSource records via the admin API or directly via repository

- [x] T015 [US2] Create configuration for ATO ruling ingestion (TR, TD, PCG, LCR) in `backend/app/modules/tax_planning/knowledge_seed.py`
  - Define DocID ranges for tax-planning-relevant rulings:
    - Key TRs: TR 98/1 (prepaid expenses), TR 2022/4 (s100A), TR 2021/1 (CGT), etc.
    - Key PCGs: PCG 2017/13 (Div 7A), PCG 2021/4 (s100A), etc.
    - Key TDs and LCRs relevant to tax planning strategies
  - Source type: `ato_legal_db`, collection: `compliance_knowledge`

- [x] T016 [US2] Create configuration for key legislation sections in `backend/app/modules/tax_planning/knowledge_seed.py`
  - Target key divisions/sections:
    - ITAA 1997: Div 40 (depreciation), Div 328 (SBE), Subdiv 152 (CGT concessions)
    - ITAA 1936: s82KZM (prepaid expenses), Div 7A (ss109B-109ZE)
    - FBTAA 1986: key exemptions sections
  - Source type: `legislation`, collection: `compliance_knowledge`

- [x] T017 [US2] Create a management command or Celery task to run the seed and trigger ingestion in `backend/app/modules/tax_planning/knowledge_seed.py`
  - Function that creates all knowledge sources from T014-T016
  - Function that triggers ingestion for each source
  - Idempotent: skip sources that already exist

- [ ] T018 [US2] Run ingestion and verify content in the knowledge base
  - Execute the seed script / trigger ingestion
  - Verify via admin UI Search Test tab:
    - "prepaid expenses 12 month rule" → returns ATO content
    - "instant asset write-off threshold" → returns current threshold guidance
    - "Division 7A private company" → returns Div 7A guidance
  - Verify ingestion job stats show items processed

**Checkpoint**: Knowledge base is populated and searchable. RAG retrieval in Phase 3 now returns real ATO content.

---

## Phase 5: User Story 3 — Citation Verification and Confidence Indicators (Priority: P2)

**Goal**: Accountant sees a clear visual indicator of how trustworthy the citations are.

**Independent Test**: Generate a response with citations and verify the verification badge accurately reflects whether citations match indexed content.

### Implementation for User Story 3

_Note: Most of the verification logic was implemented in Phase 2 (T008) and the badge in Phase 3 (T011-T013). This phase handles edge cases and refinements._

- [x] T019 [US3] Handle the "no citations" case in citation verification in `backend/app/modules/tax_planning/service.py`
  - When CitationVerifier finds zero citations in the response, return status `"no_citations"` instead of running verification
  - When knowledge base retrieval returns zero results, skip verification entirely and return `"no_citations"`

- [x] T020 [US3] Add superseded ruling detection in `backend/app/modules/tax_planning/service.py`
  - When retrieved chunks have `is_superseded: true` in metadata, append a note to the reference material: "(Note: this ruling has been superseded — check for current version)"
  - Claude will naturally incorporate this caveat in the response

- [x] T021 [US3] Refine CitationBadge with tooltip details in `frontend/src/components/tax-planning/CitationBadge.tsx`
  - Add a tooltip (shadcn `Tooltip` component) showing: "X of Y citations verified against knowledge base"
  - For `partially_verified`: list which citations were not verified

**Checkpoint**: Verification indicators are accurate, edge cases handled, accountant has full transparency.

---

## Phase 6: User Story 4 — Entity-Specific and FY-Aware Retrieval (Priority: P2)

**Goal**: Retrieval returns entity-appropriate content — company queries get company guidance, trust queries get trust guidance.

**Independent Test**: Create tax plans for different entity types, ask the same question, and verify that retrieved content differs by entity type.

### Implementation for User Story 4

- [x] T022 [US4] Build entity-type metadata filter in `backend/app/modules/tax_planning/service.py`
  - In the retrieval step (T007), construct a Pinecone metadata filter: `entity_types` contains the plan's `entity_type`
  - Map entity types: `company` → filter for chunks tagged with `company`, `individual` → `sole_trader` or `individual`, etc.
  - Use as an optional filter — if no entity-type-tagged content exists, fall back to unfiltered results

- [x] T023 [US4] Add financial year preference to retrieval in `backend/app/modules/tax_planning/service.py`
  - When constructing the search query, append the financial year (e.g., "FY 2025-26") to help semantic search prefer FY-relevant content
  - If `fy_applicable` metadata is available on chunks, use as a soft filter (prefer matching FY, don't exclude others)

- [x] T024 [US4] Add topic tag enrichment from plan context in `backend/app/modules/tax_planning/service.py`
  - Based on the plan's entity_type, inject relevant topic tags into the retrieval query:
    - Company → `income_tax`, `small_business`, `division_7a`
    - Individual → `income_tax`, `deductions`, `cgt`
    - Trust → `trusts`, `income_tax`, `cgt`
    - Partnership → `income_tax`, `deductions`
  - These augment (not replace) the QueryRouter's classification

**Checkpoint**: Entity-specific retrieval works — different entity types get appropriately filtered content.

---

## Phase 7: Tests

**Purpose**: Unit and integration tests for RAG integration

- [ ] T025 [P] Create unit tests for `format_reference_material()` in `backend/tests/unit/modules/tax_planning/test_prompts.py`
  - Test empty chunks returns empty string
  - Test single chunk formats correctly with title, identifier, text
  - Test max 5 chunks respected
  - Test text truncation

- [ ] T026 [P] Create unit tests for RAG retrieval logic in `backend/tests/unit/modules/tax_planning/test_rag_integration.py`
  - Mock KnowledgeService.search_knowledge() and verify it's called with correct filters
  - Test conversational messages skip retrieval
  - Test entity_type filter construction
  - Test reference_material is passed to agent

- [ ] T027 [P] Create unit tests for citation verification saving in `backend/tests/unit/modules/tax_planning/test_citation_verification.py`
  - Mock CitationVerifier.verify() and verify result is saved on message
  - Test "no_citations" case when no citations found
  - Test verification SSE event is yielded

- [ ] T028 Create integration test for the full chat endpoint with RAG in `backend/tests/integration/modules/tax_planning/test_chat_with_rag.py`
  - Test POST /api/v1/tax-plans/{id}/chat/stream with a populated knowledge base
  - Verify response SSE events include `verification` event
  - Verify saved message has `source_chunks_used` and `citation_verification` populated

- [ ] T029 Run full validation suite
  - Run: `cd backend && uv run ruff check . && uv run pytest`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - Verify all tests pass, no lint errors

**Checkpoint**: All tests pass, full validation suite green.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [x] T030 [P] Add audit logging for RAG retrieval events in `backend/app/modules/tax_planning/service.py`
  - Log `tax_planning.rag.retrieval` event with query, entity_type, FY, result count, top scores
  - Log `tax_planning.citation.verified` event with message_id, citation counts, verification rate

- [x] T031 Update the existing tax plan disclaimer to note that citations are informational in `backend/app/modules/tax_planning/prompts.py`
  - Ensure the system prompt preserves: "This is an estimate only and does not constitute formal tax advice"
  - Add: "Citations reference publicly available ATO guidance for informational purposes"

- [ ] T032 Run quickstart.md validation
  - Follow all steps in `specs/050-rag-tax-planning/quickstart.md`
  - Verify each step works as documented
  - Fix any discrepancies

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run ruff check . && uv run pytest`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - All tests must pass before PR

- [ ] TFINAL-2 Push feature branch and create PR
  - Run: `git push -u origin 050-rag-tax-planning`
  - Run: `gh pr create --title "Spec 050: RAG-Grounded Tax Planning" --body "..."`
  - Include summary: RAG integration into tax planning agent, citation display, knowledge base population

- [ ] TFINAL-3 Address review feedback (if any)

- [ ] TFINAL-4 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-5 Update ROADMAP.md
  - Mark spec 050 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: MUST be done first
- **Phase 1 (Setup)**: Migration + model/schema changes — blocks all phases
- **Phase 2 (Foundational)**: RAG wiring — blocks Phase 3
- **Phase 3 (US1 — Cited Advice)**: Frontend display — depends on Phase 2. This is the **MVP**.
- **Phase 4 (US2 — KB Population)**: Independent of Phase 3 — can run in parallel. Improves US1 quality.
- **Phase 5 (US3 — Verification)**: Refinements — depends on Phase 3 (badge exists)
- **Phase 6 (US4 — Entity Filtering)**: Depends on Phase 2 (retrieval exists)
- **Phase 7 (Tests)**: Depends on Phases 2-6 being complete
- **Phase 8 (Polish)**: Depends on all user stories

### User Story Dependencies

- **US1 (Cited Advice)**: Depends on Phase 2 (foundational). Can work with empty KB (shows "general knowledge" badge).
- **US2 (KB Population)**: Independent — can run at any time after Phase 1. Enhances US1 but not required.
- **US3 (Verification)**: Depends on US1 (badge component and verification event).
- **US4 (Entity Filtering)**: Depends on Phase 2 (retrieval logic). Independent of US1/US3.

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel (model + schema)
- **Phase 2**: T004 and T005 can run in parallel (both in prompts.py but different functions)
- **Phase 3**: T010 and T011 can run in parallel (different files)
- **Phase 4**: T014, T015, T016 can all run in parallel (all adding to same seed file but different sections)
- **Phase 7**: T025, T026, T027 can all run in parallel (different test files)
- **US1 and US2 can run in parallel** after Phase 2

---

## Parallel Example: Phases 3 + 4

```bash
# These can run in parallel after Phase 2:

# Thread 1: US1 — Frontend citation display
Task: T010 "Update types in frontend/src/types/tax-planning.ts"
Task: T011 "Create CitationBadge in frontend/src/components/tax-planning/CitationBadge.tsx"
Task: T012 "Handle verification SSE event in ScenarioChat.tsx"
Task: T013 "Render CitationBadge in ScenarioChat.tsx"

# Thread 2: US2 — Knowledge base population
Task: T014 "Create ATO topic page source config"
Task: T015 "Create ATO ruling source config"
Task: T016 "Create legislation source config"
Task: T017 "Create seed command"
Task: T018 "Run ingestion and verify"
```

---

## Implementation Strategy

### MVP First (Phase 1 + 2 + 3)

1. Complete Phase 1: Setup (migration, model, schema)
2. Complete Phase 2: Foundational (RAG wiring)
3. Complete Phase 3: US1 (citation display)
4. **STOP and VALIDATE**: Test with empty KB — should show "General knowledge" badge
5. Then populate KB (Phase 4) to get real citations

### Incremental Delivery

1. Phase 1+2 → RAG wiring complete
2. Add US1 → Citations visible in chat (MVP!)
3. Add US2 → Real ATO content in KB → citations become meaningful
4. Add US3 → Verification refinements → accountant trust
5. Add US4 → Entity-specific retrieval → better relevance

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Knowledge base population (US2) improves quality but US1 works without it (graceful degradation)
- The seed script in Phase 4 should be idempotent for re-runs
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
