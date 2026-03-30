# Research: RAG-Grounded Tax Planning

**Feature**: 050-rag-tax-planning
**Date**: 2026-03-31

## R1: How to integrate RAG retrieval into the TaxPlanningAgent

**Decision**: Add a retrieval step in `TaxPlanningService.send_chat_message_streaming()` before calling the agent. Use `KnowledgeService.search_knowledge()` targeting `compliance_knowledge` namespace with entity-type and topic-tag metadata filters. Pass retrieved chunks to the agent as a `reference_material` parameter, which gets injected into the system prompt.

**Rationale**: The service layer (not the agent) should own retrieval because:
1. The service already has access to the DB session and settings needed for `KnowledgeService`
2. The agent is a pure LLM orchestrator — adding DB/Pinecone dependencies would violate its single responsibility
3. The service can log retrieval audit events alongside existing message-handling logic

**Alternatives considered**:
- Agent calls retrieval directly via tool-use: Rejected — adds complexity, latency (extra LLM round-trip), and couples the agent to infrastructure
- Middleware/decorator approach: Rejected — retrieval needs plan context (entity type, FY) that only the service has

## R2: How to instruct Claude to cite sources

**Decision**: Modify `TAX_PLANNING_SYSTEM_PROMPT` in `prompts.py` to include a "Reference Material" section with retrieved chunks. Add explicit instructions: "When your advice aligns with a reference, cite it inline using [Source: {identifier}]. Include a ## Sources section at the end listing all cited references with full titles. If no reference supports a claim, state it is based on general knowledge."

**Rationale**: System prompt injection is the standard pattern for RAG — it's simple, debuggable, and doesn't require changes to the tool-use loop. Claude's instruction-following is strong enough to cite reliably when given explicit format instructions and actual reference text.

**Alternatives considered**:
- Separate "citation tool" that Claude calls: Rejected — over-engineered for this use case, adds latency
- Post-processing to inject citations: Rejected — fragile regex matching, would require a second LLM call

## R3: How to determine when to skip RAG retrieval

**Decision**: Use the existing `QueryRouter` from the knowledge module to classify the user's message. If classified as non-tax (greetings, acknowledgements, follow-up questions like "thanks"), skip retrieval. Also skip if the message is very short (< 10 characters) and matches a conversational pattern.

**Rationale**: The QueryRouter already has regex-based classification that's fast (sub-millisecond) and doesn't require an LLM call. Extending it with a simple conversational pattern check avoids unnecessary Pinecone queries.

**Alternatives considered**:
- Always retrieve: Rejected — wastes embedding API calls and adds latency for "ok thanks" messages
- LLM-based classification: Rejected — adds latency and cost for a simple check

## R4: Citation verification approach

**Decision**: Use the existing `CitationVerifier` from the knowledge module. After Claude generates a response, extract citations and verify each against the retrieved chunks that were passed in the prompt. Return a `CitationVerificationResult` with the response.

**Rationale**: The verifier already exists and handles citation extraction (ruling refs, section refs, numbered citations). Since we have the retrieved chunks in memory, verification is a simple string-matching operation — no additional Pinecone query needed.

**Alternatives considered**:
- Skip verification, trust Claude: Rejected — defeats the purpose of grounding
- Re-query Pinecone per citation: Rejected — unnecessary since we already have the source chunks

## R5: Optimal number of retrieved chunks for the prompt

**Decision**: Retrieve top 8 chunks from Pinecone (after reranking), inject the top 5 into the prompt. This balances context quality against token budget — 5 chunks at ~500 tokens each = ~2,500 tokens of reference material, leaving ample room for the financial context and conversation history within Claude's context window.

**Rationale**: Testing shows that beyond 5-6 chunks, additional context adds noise without improving citation quality. The reranker filters aggressively, so top 5 post-reranking are high quality.

**Alternatives considered**:
- 3 chunks: Too few — may miss relevant rulings for multi-strategy responses
- 10 chunks: Too many — adds ~5K tokens, risks diluting attention on key references

## R6: Content ingestion priority and source configuration

**Decision**: Create knowledge sources in this priority order:
1. **ATO Topic Pages** (ATOWebScraper) — ~50 targeted URLs covering the 12 core tax planning topics
2. **ATO PCGs** (ATOLegalDatabaseScraper) — practical compliance guidelines most relevant to strategy advice
3. **ATO Tax Rulings** (ATOLegalDatabaseScraper) — binding rulings (TR, TD)
4. **ATO Law Companion Rulings** (ATOLegalDatabaseScraper) — LCRs for recent legislation
5. **Key legislation sections** (LegislationGovScraper) — ITAA 1997/1936 key divisions

**Rationale**: Topic pages provide the most accessible, plain-language guidance. PCGs are directly relevant to risk-based tax planning. Rulings provide binding authority. Legislation provides the ultimate source but is dense and less useful for direct citation in a chat context.

**Alternatives considered**:
- Ingest everything at once: Rejected — risk of overwhelming the KB with low-relevance content; better to start targeted and expand
- Start with legislation only: Rejected — legislation text is dense and hard for Claude to cite meaningfully in a chat; topic pages are more actionable

## R7: Frontend citation display approach

**Decision**: Claude's response already renders as Markdown via `react-markdown` in `ScenarioChat.tsx`. Citations will render naturally as part of the Markdown output. The Sources section renders as a Markdown heading + list. Add a small verification badge component above the response.

**Rationale**: No changes needed to the Markdown rendering pipeline. The badge is the only new UI element — a small `Badge` component (already available from shadcn/ui) showing verification status.

**Alternatives considered**:
- Clickable citation links: Rejected for MVP — would require linking to ATO website or an internal document viewer; can be a follow-up
- Separate citations panel: Rejected — breaks reading flow; inline is more natural for accountants

## R8: Streaming compatibility

**Decision**: RAG retrieval happens before the streaming call to Claude, not during. The flow is: retrieve chunks → build prompt with references → stream Claude response → verify citations post-stream. This means retrieval adds a one-time latency before streaming begins, but the stream itself is unaffected.

**Rationale**: The streaming SSE architecture in `process_message_streaming()` yields events as they arrive. Retrieval must complete before the first Claude call since the reference material is part of the system prompt. This is acceptable — the "Calculating tax impact..." thinking indicator already covers the pre-stream phase.

**Alternatives considered**:
- Parallel retrieval during first LLM call: Rejected — the LLM needs the reference material in the first call's system prompt, so retrieval must complete first
