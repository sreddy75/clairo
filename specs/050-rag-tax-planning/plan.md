# Implementation Plan: RAG-Grounded Tax Planning

**Branch**: `050-rag-tax-planning` | **Date**: 2026-03-31 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/050-rag-tax-planning/spec.md`

## Summary

Integrate the existing knowledge/RAG retrieval pipeline into the tax planning AI agent so that strategy recommendations cite authoritative ATO sources. The agent retrieves relevant content from Pinecone before calling Claude, injects it as reference material in the system prompt, and Claude cites specific rulings/legislation inline. Responses display a Sources section and a citation verification badge. The knowledge base is populated with tax planning-specific ATO content using existing scrapers.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, anthropic SDK, Voyage 3.5 lite, Pinecone, sentence-transformers (cross-encoder reranker)
**Storage**: PostgreSQL 16 (2 new JSONB columns on `tax_plan_messages`), Pinecone `clairo-knowledge` index (`compliance_knowledge` namespace)
**Testing**: pytest with pytest-asyncio
**Target Platform**: Linux server (Docker), Vercel (frontend)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: RAG retrieval adds < 3 seconds to response time (per constitution Layer 3 standard)
**Constraints**: Must use existing knowledge module infrastructure; no new Pinecone indexes or namespaces
**Scale/Scope**: ~50 ATO topic pages + ~300 rulings (TR/TD/PCG/LCR) + key legislation sections

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Layer ordering (L3 after L1/L2) | PASS | Layer 3 feature; L1/L2 are complete |
| Modular monolith boundaries | PASS | Tax planning service calls knowledge service via public interface; no cross-module DB access |
| Repository pattern | PASS | All DB access via existing repositories |
| Multi-tenancy (tenant_id) | PASS | Knowledge content is shared (no tenant_id); tax plan messages already have tenant_id |
| Audit trail | PASS | Three audit events defined: retrieval, ingestion, citation verification |
| Human-in-the-loop | PASS | AI suggests with citations; accountant reviews and decides |
| Source citations on all answers | PASS | This feature directly implements this constitution requirement |
| RAG retrieval < 3 seconds | PASS | Targeted in SC-005 |
| Testing (80% unit, 100% endpoints) | PASS | Test plan covers unit + integration |
| No tax advice (information only) | PASS | Disclaimer preserved; citations are informational |

**Post-Phase 1 re-check**: PASS — No violations. Design uses existing modules via service interfaces.

## Project Structure

### Documentation (this feature)

```text
specs/050-rag-tax-planning/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Developer quickstart
├── contracts/           # API contract changes
│   └── api-changes.md   # Modified endpoint contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── tax_planning/
│   │   │   ├── agent.py            # MODIFIED: Accept reference_material param
│   │   │   ├── prompts.py          # MODIFIED: Add citation instructions + reference material formatting
│   │   │   ├── service.py          # MODIFIED: Add RAG retrieval before agent call
│   │   │   ├── models.py           # MODIFIED: Add source_chunks_used, citation_verification to TaxPlanMessage
│   │   │   └── schemas.py          # MODIFIED: Add new fields to message response
│   │   └── knowledge/
│   │       ├── service.py          # USED AS-IS: search_knowledge()
│   │       ├── retrieval/          # USED AS-IS: hybrid_search, query_router, reranker, citation_verifier
│   │       └── scrapers/           # USED AS-IS: ato_web, ato_legal_db, legislation_gov
│   └── tasks/
│       └── knowledge.py            # USED AS-IS: Celery ingestion tasks
└── tests/
    └── unit/
        └── modules/
            └── tax_planning/
                ├── test_rag_integration.py   # NEW: RAG retrieval integration tests
                └── test_citation_display.py  # NEW: Citation verification tests

frontend/
├── src/
│   ├── components/
│   │   └── tax-planning/
│   │       ├── ScenarioChat.tsx      # MODIFIED: Handle verification SSE event
│   │       └── CitationBadge.tsx     # NEW: Verification badge component
│   └── types/
│       └── tax-planning.ts          # MODIFIED: Add citation fields to message type
```

**Structure Decision**: Standard Clairo modular monolith. All changes within existing `tax_planning` module + one new frontend component. Knowledge module used as-is via its public service interface.

## Implementation Phases

### Phase 1: Backend RAG Integration (P1 — Story 1 core)

1. **Alembic migration**: Add `source_chunks_used` (JSONB, nullable) and `citation_verification` (JSONB, nullable) to `tax_plan_messages` table.

2. **Update TaxPlanMessage model** (`models.py`): Add the two new JSONB columns.

3. **Update schemas** (`schemas.py`): Add `source_chunks_used` and `citation_verification` to the message response schema. Both optional.

4. **Update prompts** (`prompts.py`):
   - Add `format_reference_material(chunks)` function that formats retrieved chunks as numbered references with source attribution
   - Update `TAX_PLANNING_SYSTEM_PROMPT` to include citation instructions: cite sources inline, include Sources section, note when advice is general knowledge
   - Add `{reference_material}` placeholder to the system prompt template

5. **Update agent** (`agent.py`):
   - Add `reference_material: str | None = None` parameter to `process_message()` and `process_message_streaming()`
   - Pass reference material into `_build_system_prompt()` so it gets included in the prompt

6. **Update service** (`service.py`):
   - Import `KnowledgeService` and `QueryRouter` from knowledge module
   - In `send_chat_message_streaming()`, before calling the agent:
     a. Classify query via `QueryRouter` — skip retrieval if conversational
     b. Call `KnowledgeService.search_knowledge()` with query, entity_type filter, topic_tags
     c. Format top 5 reranked chunks as reference material
     d. Pass to agent
   - After streaming completes:
     a. Run `CitationVerifier.verify()` on the response content against retrieved chunks
     b. Yield a `verification` SSE event with the result
     c. Save `source_chunks_used` and `citation_verification` on the assistant message record

### Phase 2: Frontend Citation Display (P1 — Story 1 UI)

1. **Update types** (`types/tax-planning.ts`): Add `source_chunks_used` and `citation_verification` fields to the message type. Add `VerificationStatus` type.

2. **Create CitationBadge component** (`CitationBadge.tsx`): A small `Badge` component that displays:
   - Green "Sources verified" when verification_rate >= 0.9
   - Amber "Some sources unverified" when 0.5 <= rate < 0.9
   - Red "Sources could not be verified" when rate < 0.5
   - Stone "General knowledge" when no citations present

3. **Update ScenarioChat** (`ScenarioChat.tsx`):
   - Handle new `verification` SSE event type — store verification result in message state
   - Render `CitationBadge` below assistant messages that have verification data
   - For loaded historical messages, read `citation_verification` from the message object

### Phase 3: Knowledge Base Population (P1 — Story 2)

1. **Configure ATO topic page sources**: Create knowledge sources via admin UI (or seed script) for the 12 core tax planning topics with targeted URLs.

2. **Configure ATO ruling sources**: Create knowledge sources for TR, TD, PCG, LCR ingestion via the ATO Legal Database scraper with relevant DocID ranges.

3. **Configure legislation sources**: Ensure the legislation scraper is configured for key tax planning divisions (ITAA 1997 Div 40, Div 328, Subdiv 152; ITAA 1936 s82KZM, Div 7A).

4. **Run ingestion**: Trigger scraper jobs via admin UI or Celery tasks. Monitor via Jobs tab.

5. **Verify content**: Use the Search Test tab to validate retrieval quality for key tax planning queries.

### Phase 4: Entity-Aware Retrieval (P2 — Story 4)

1. **Build metadata filters**: In the service retrieval step, construct Pinecone metadata filters from the plan's `entity_type`. Map entity types to filter values matching the `entity_types` metadata field on content chunks.

2. **Add FY filtering**: When available, include `fy_applicable` in the metadata filter to prefer FY-specific content.

3. **Test with different entity types**: Verify that company queries return company-relevant content, trust queries return trust content, etc.

### Phase 5: Tests

1. **Unit tests for RAG integration**: Test that the service calls retrieval, passes chunks to agent, and saves metadata on the message.
2. **Unit tests for citation verification**: Test the verification flow with mocked chunks and responses.
3. **Unit tests for prompt formatting**: Test that reference material is correctly formatted and injected.
4. **Integration tests**: Test the full chat endpoint with a populated knowledge base to verify citations appear in responses.

## Complexity Tracking

No constitution violations. All changes are within existing module boundaries using established patterns.
