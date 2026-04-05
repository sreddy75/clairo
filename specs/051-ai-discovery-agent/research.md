# Research: AI Discovery Agent

**Branch**: `051-ai-discovery-agent` | **Date**: 2026-04-04

## R1: Passwordless Auth for External Accountants

**Decision**: Adapt the existing portal magic link auth system (`MagicLinkService`) for discovery contacts.

**Rationale**: The portal already implements the complete passwordless flow: token generation → SHA-256 hash for storage → email via Resend → verify → JWT session (access + refresh tokens). The pattern is identical to what discovery needs — the only difference is the subject entity (discovery contact vs. XeroConnection).

**What to reuse**:
- `MagicLinkService` for token generation, hashing, JWT creation (`portal/auth/magic_link.py`)
- `PortalSession` pattern for session management (7-day session, 15-min access tokens)
- `portalTokenStorage` pattern on frontend (`portal.ts:208-243`)
- `authenticatedFetch()` pattern for API calls
- Login/verify page UI patterns (`portal/login/page.tsx`, `portal/verify/page.tsx`)

**What to create new**:
- `DiscoveryContact` model (replaces `PortalInvitation.connection_id` with `contact.email` as identity)
- `DiscoverySession` model for auth sessions (parallel to `PortalSession`)
- Discovery-specific JWT claims: `sub=contact_id`, `token_type="discovery_access"`
- `CurrentDiscoveryContact` dependency (parallel to `CurrentPortalClient`)
- Invitation flow from admin panel (tenant invites contact by email)

**Alternatives considered**:
- Clerk for discovery contacts — rejected: too heavy for external non-subscribers
- Simple password auth — rejected: adds friction, password management burden
- OTP codes only (no magic link) — could work as supplementary, but email link is the primary pattern already proven in portal

## R2: Generative UI / Dynamic Components in Chat

**Decision**: Use the existing A2UI (Agent-to-User Interface) system. It already supports `fileUpload`, streaming rendering, data binding, and action dispatch.

**Rationale**: A complete generative UI system already exists in Clairo:
- **Backend**: `core/a2ui/` — schemas, builder, 30+ component types including `fileUpload` (line 78 in schemas.py)
- **Frontend**: `lib/a2ui/` — renderer, streaming renderer, component catalog, data binding context, action dispatch
- **Integration**: The assistant page already renders A2UI components inline in chat (line 1348 in assistant/page.tsx)
- **LLM-driven**: `a2ui_llm.py` — LLM can request UI components via fenced code blocks in response
- **Builder pattern**: Fluent `A2UIBuilder` for programmatic component construction

**What to reuse**:
- Full A2UI type system, builder, renderer, streaming renderer
- `fileUpload` component type (already in catalog)
- `A2UIRenderer` integration pattern from assistant page
- LLM-driven A2UI generation path

**What to create new**:
- `workflowBuilder` component type — drag/reorder process steps
- `painRanker` component type — drag-rank pain points
- `segmentEstimator` component type — client volume/characteristics inputs
- `schemaPreview` component type — CSV column/file structure preview
- Wire action handlers to send data back into discovery chat stream
- Discovery-specific A2UI prompt schema (telling the LLM about available components)

**Alternatives considered**:
- Build custom components outside A2UI — rejected: duplicates existing infrastructure
- Use only LLM-driven generation — rejected for discovery: some components should be triggered by explicit skill logic (rule-based), not left to LLM discretion

## R3: Multi-Session Continuity and Living Discovery State

**Decision**: Store the discovery state as a structured JSONB column on a `DiscoveryState` model, updated by the agent at session end. The agent reads it at session start.

**Rationale**: The existing chat systems persist messages but don't maintain a structured summary. The discovery agent needs something richer — a living document that captures what's been learned across all sessions.

**State structure** (JSONB):
```json
{
  "workflows": {
    "uber-driver-bas": {
      "name": "Uber Driver BAS Preparation",
      "status": "in_progress",
      "completeness": 0.7,
      "data_inputs": { "items": [...], "gaps": [...] },
      "process_steps": { "items": [...], "confirmed": true },
      "outputs": { "items": [...], "gaps": [...] },
      "pain_points": { "items": [...], "ranked": true },
      "volume": { "count": 35, "revenue_per": null },
      "edge_cases": { "items": [...] }
    }
  },
  "open_threads": ["spreadsheet template — follow up"],
  "last_session_summary": "Discussed Uber driver workflow...",
  "version": 3
}
```

**Session diff computation**: On session start, compare current state with `last_session_snapshot` (stored at session end). Any changes from cross-interview insights or admin edits are surfaced in the agent's greeting.

**Alternatives considered**:
- Store state as a text document (Markdown) — rejected: harder to compute diffs and query completeness
- Reconstruct state from message history on each session — rejected: slow, expensive, and loses manual corrections
- Store in a separate document store — rejected: JSONB in PostgreSQL is sufficient for this scale

## R4: Skill-Based Agent Architecture

**Decision**: Implement discovery agent as a set of discrete skills following the `agent.py` / `prompts.py` pattern from tax planning, but with explicit skill definitions.

**Rationale**: The spec requires skills for workflow extraction, pain point capture, artifact analysis, and cross-interview comparison. Each skill has different data needs, prompts, output schemas, and state updates.

**Skills**:
1. `conversation_guide` — Main skill: reads discovery state, decides what topic to explore, generates natural conversation
2. `extraction` — Processes conversation segments to extract structured data (workflow steps, pain points, tool mentions)
3. `artifact_analysis` — Analyses uploaded files (CSV structure, PDF content) and generates schema previews
4. `state_updater` — Updates the living discovery state after extraction is confirmed
5. `cross_interview` — Compares current session insights against other contacts' data for the same workflow type
6. `session_summariser` — Generates session summary and diffs at session start/end

**Pattern**: Each skill is a function/class with:
- Input: relevant slice of discovery state + conversation context
- System prompt: from `prompts.py`
- Output schema: Pydantic model for structured extraction
- State update: what changes in discovery state after execution

**Alternatives considered**:
- Single monolithic agent — rejected: different skills need different context windows and prompts
- External agent orchestrator (LangChain/LangGraph) — rejected: Clairo uses direct Anthropic SDK, constitution prohibits LangChain

## R5: Cross-Accountant Aggregation and Semantic Matching

**Decision**: Use Voyage 3.5 lite embeddings (already in use for knowledge RAG) for semantic workflow matching. Store workflow descriptions as embeddings for similarity comparison.

**Rationale**: The spec requires matching "rideshare drivers" = "Uber clients" = "gig economy workers." Keyword matching won't work. Voyage embeddings with cosine similarity will.

**Approach**:
- When a new workflow is identified, embed its description via Voyage 3.5 lite
- Compare against existing workflow embeddings with cosine similarity threshold
- Above threshold → suggest link to admin (never auto-merge)
- Aggregation queries use SQL GROUP BY on workflow linkages with frequency counts

**Storage**: Workflow embeddings stored in a `workflow_embedding` vector column on the `DiscoveryWorkflow` model (pgvector, 1024 dims to match Voyage 3.5 lite).

**Alternatives considered**:
- Pinecone for workflow embeddings — rejected: overkill for <100 workflows, pgvector in PostgreSQL is sufficient
- LLM-based comparison only — rejected: expensive per query, embeddings are a better first-pass filter
- Manual linking only — rejected: doesn't scale, misses non-obvious matches
