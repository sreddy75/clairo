# Feature Specification: RAG-Grounded Tax Planning

**Feature Branch**: `050-rag-tax-planning`
**Created**: 2026-03-31
**Status**: Draft
**Input**: User description: "RAG-Grounded Tax Planning: Integrate the existing knowledge/RAG system into the tax planning AI agent so that strategy recommendations cite authoritative ATO sources (rulings, legislation, PCGs). The agent should retrieve relevant content from Pinecone before calling Claude, inject it as reference material, and instruct Claude to cite specific sections/rulings. Responses should show inline citations and a sources section. Also need to populate the knowledge base with tax planning-specific content by running the existing scrapers against ATO topic pages, rulings (TR, TD, PCG, LCR), and key legislation sections."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accountant Receives Cited Tax Planning Advice (Priority: P1)

An accountant opens the Tax Planning tab for a client, asks "what's the best strategy to save tax?", and receives strategy recommendations that include inline citations to specific ATO rulings, legislation sections, and practical compliance guidelines. Each recommendation references the authoritative source (e.g., "Per s82KZM ITAA 1936, prepaid expenses are deductible under the 12-month rule..."). A "Sources" section at the bottom of the response lists all referenced documents with their full titles.

**Why this priority**: This is the core value proposition — accountants need confidence that AI-generated strategies are grounded in real ATO guidance, not hallucinated. Without citations, the feature is an unverifiable opinion generator.

**Independent Test**: Can be tested by asking the tax planning chat a strategy question and verifying that the response contains inline citations matching documents in the knowledge base, and that a Sources section appears with valid references.

**Acceptance Scenarios**:

1. **Given** a tax plan with financials loaded and the knowledge base populated with ATO content, **When** the accountant asks "what strategies can I use to reduce tax?", **Then** the response includes at least one inline citation referencing a specific ATO ruling, legislation section, or PCG.
2. **Given** a strategy recommendation citing "TR 98/1", **When** the accountant reads the Sources section, **Then** "TR 98/1" appears with its full title and a brief description of its relevance.
3. **Given** a query about instant asset write-off, **When** the agent responds, **Then** the response cites the current threshold and references the relevant ATO guidance page or legislation section.
4. **Given** the knowledge base has no relevant content for an obscure query, **When** the agent responds, **Then** the response clearly states that no authoritative source was found and marks the advice as based on general knowledge only.

---

### User Story 2 - Knowledge Base Populated with Tax Planning Content (Priority: P1)

A platform administrator uses the existing Knowledge Base admin interface to trigger ingestion of tax planning-specific content. The system scrapes ATO topic pages (instant asset write-off, prepaid expenses, Division 7A, SBE concessions, CGT concessions, FBT exemptions, super contributions, loss carry-back), ATO rulings (TR, TD, PCG, LCR), and key legislation sections. The content is chunked, embedded, and stored in Pinecone ready for retrieval.

**Why this priority**: Without content in the knowledge base, the RAG integration has nothing to retrieve. This is a prerequisite for Story 1.

**Independent Test**: Can be tested by triggering ingestion via the admin UI, then querying the knowledge base search test tab to verify that tax planning content returns relevant results for queries like "prepaid expenses deduction" or "instant asset write-off threshold".

**Acceptance Scenarios**:

1. **Given** configured knowledge sources for ATO topic pages, **When** the admin triggers ingestion, **Then** the system scrapes and indexes at least 30 key ATO guidance pages covering the core tax planning topics.
2. **Given** configured knowledge sources for ATO rulings, **When** the admin triggers ingestion, **Then** the system scrapes and indexes Tax Rulings (TR), Tax Determinations (TD), Practical Compliance Guidelines (PCG), and Law Companion Rulings (LCR) relevant to tax planning.
3. **Given** ingested content, **When** the admin searches "prepaid expenses 12 month rule" in the search test tab, **Then** results include chunks from TR 98/1 or equivalent ATO guidance with relevance scores above the quality threshold.
4. **Given** a completed ingestion run, **When** the admin views the Jobs tab, **Then** the job shows items processed, added, skipped, and any errors encountered.

---

### User Story 3 - Citation Verification and Confidence Indicators (Priority: P2)

After the AI generates a response with citations, the system verifies each citation against the retrieved knowledge base content. The accountant sees a confidence indicator on the response — either "Sources verified" when all citations match indexed content, or a warning when citations could not be verified. This gives the accountant a clear signal about how much to trust the response.

**Why this priority**: Citations without verification could be worse than no citations — a hallucinated citation to a non-existent ruling erodes trust more than an uncited opinion. Verification is the trust layer.

**Independent Test**: Can be tested by generating a response and checking that the verification badge accurately reflects whether cited documents exist in the knowledge base.

**Acceptance Scenarios**:

1. **Given** a response where all inline citations match documents in the knowledge base, **When** the response is displayed, **Then** a "Sources verified" indicator appears.
2. **Given** a response where the AI cites a ruling not found in the knowledge base, **When** the response is displayed, **Then** a warning indicator appears noting that some citations could not be verified.
3. **Given** a response with no citations (general advice), **When** the response is displayed, **Then** a neutral indicator appears noting that the response is based on general knowledge without specific source citations.

---

### User Story 4 - Entity-Specific and FY-Aware Retrieval (Priority: P2)

When the accountant asks a tax planning question, the retrieval system considers the client's entity type (company, individual, trust, partnership) and financial year to return the most relevant content. A company query about tax rates retrieves small business entity concessions and company tax rate thresholds, not individual tax bracket information. FY-specific thresholds (e.g., instant asset write-off limits that change annually) return the correct values for the plan's financial year.

**Why this priority**: Generic retrieval that ignores entity type and FY would return irrelevant or misleading content, undermining the accuracy of the grounded advice.

**Independent Test**: Can be tested by creating tax plans for different entity types and verifying that the same question returns entity-appropriate citations.

**Acceptance Scenarios**:

1. **Given** a tax plan for a company entity, **When** the accountant asks about tax rate, **Then** retrieved content focuses on company tax rates and base rate entity rules, not individual tax brackets.
2. **Given** a tax plan for FY 2025-26, **When** the accountant asks about instant asset write-off, **Then** the response cites the threshold applicable to FY 2025-26, not a previous year's threshold.
3. **Given** a tax plan for a trust entity, **When** the accountant asks about distribution strategies, **Then** retrieved content includes Section 100A guidance and trust-specific rulings.

---

### Edge Cases

- What happens when the knowledge base is empty or uninitialised? The agent should fall back to ungrounded responses with a clear warning that no authoritative sources are available.
- What happens when the ATO scraper encounters rate limiting or connection failures? The ingestion job should report the error, skip the failed item, and continue processing remaining items.
- What happens when a cited ruling has been superseded? The response should note when a ruling is marked as superseded in the knowledge base and direct the accountant to check the current version.
- What happens when the user's question is conversational ("thanks" or "ok") rather than a tax query? The system should skip RAG retrieval for non-tax queries to avoid irrelevant citations.
- What happens when multiple conflicting rulings are retrieved? The response should present both with their respective dates and note the conflict for the accountant to resolve.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST retrieve relevant knowledge base content before generating tax planning responses, using the user's question, entity type, and financial year as retrieval context.
- **FR-002**: System MUST inject retrieved content into the AI prompt as reference material with source attribution (ruling number, legislation section, document title).
- **FR-003**: AI responses MUST include inline citations in the format "[Source: TR 98/1]" or "[Source: s82KZM ITAA 1936]" when referencing specific ATO content.
- **FR-004**: Each response with citations MUST include a "Sources" section listing all referenced documents with their full titles.
- **FR-005**: System MUST verify citations against the knowledge base and display a confidence indicator (verified, partially verified, unverified, or no citations).
- **FR-006**: System MUST support ingestion of ATO topic pages, Tax Rulings (TR), Tax Determinations (TD), Practical Compliance Guidelines (PCG), and Law Companion Rulings (LCR) using the existing scraper infrastructure.
- **FR-007**: System MUST support ingestion of key Australian tax legislation sections using the existing legislation scraper.
- **FR-008**: Retrieval MUST filter by entity type (company, individual, trust, partnership) when metadata is available on indexed content.
- **FR-009**: System MUST gracefully degrade when the knowledge base is empty or retrieval returns no results — responding without citations and clearly indicating the response is based on general knowledge only.
- **FR-010**: System MUST skip RAG retrieval for non-tax conversational messages (greetings, acknowledgements) to avoid irrelevant citations.
- **FR-011**: Ingestion jobs MUST be resumable — if a scrape is interrupted, subsequent runs should pick up where the previous run left off.
- **FR-012**: System MUST display a "Sources verified" or warning badge on responses based on the citation verification result.

### Key Entities

- **Knowledge Source**: A configured content source (ATO topic pages, ATO Legal Database rulings, legislation) with scrape configuration and target namespace.
- **Content Chunk**: An indexed piece of content in Pinecone with metadata including source type, ruling number, section reference, entity types, topic tags, and financial year applicability.
- **Citation**: A reference from an AI response to a specific knowledge base document, including the source identifier (ruling number or section reference) and the matched chunk.
- **Citation Verification Result**: The outcome of verifying all citations in a response — includes per-citation verification status and an overall confidence level.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No — this feature does not change authentication or authorization.
- [x] **Data Access Events**: Yes — the system retrieves ATO rulings and legislation to inform advice. The sources used should be logged.
- [x] **Data Modification Events**: Yes — ingestion creates/updates knowledge base content.
- [ ] **Integration Events**: No — no external system sync (Xero/ATO). Content is scraped from public sources.
- [ ] **Compliance Events**: No — this feature does not affect BAS lodgements or compliance status directly.

### Audit Implementation Requirements

| Event Type                      | Trigger                                | Data Captured                                                               | Retention | Sensitive Data |
|---------------------------------|----------------------------------------|-----------------------------------------------------------------------------|-----------|----------------|
| tax_planning.rag.retrieval      | RAG query executed for tax plan chat   | Query text, entity type, FY, number of results, top result scores           | 7 years   | None           |
| knowledge.ingestion.completed   | Scraper ingestion job finishes         | Source type, items processed/added/updated/skipped/failed, duration          | 7 years   | None           |
| tax_planning.citation.verified  | Citation verification on a response    | Message ID, total citations, verified count, unverified count, verification rate | 7 years   | None           |

### Compliance Considerations

- **ATO Requirements**: The platform must not present AI-generated tax advice as authoritative ATO guidance. All responses must include the existing disclaimer ("This is an estimate only and does not constitute formal tax advice").
- **Data Retention**: ATO rulings and legislation are public domain content — no special retention constraints beyond standard 7-year audit trail for the retrieval and citation verification events.
- **Access Logging**: Knowledge base admin actions (ingestion triggers, source configuration) should be visible to practice administrators.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: At least 80% of tax planning strategy responses include at least one inline citation to a specific ATO ruling, legislation section, or PCG when the knowledge base is populated.
- **SC-002**: The knowledge base contains indexed content covering the 12 core tax planning topics (instant asset write-off, prepaid expenses, Division 7A, SBE concessions, CGT concessions, FBT exemptions, superannuation contributions, loss carry-back, company tax rates, trust distributions, R&D tax incentive, PAYG variations).
- **SC-003**: Citation verification rate exceeds 90% — meaning 9 out of 10 citations in AI responses can be matched to actual documents in the knowledge base.
- **SC-004**: Accountants can identify the authoritative source for any strategy recommendation within 5 seconds by reading the inline citation and Sources section.
- **SC-005**: Retrieval adds less than 3 seconds to the total response time compared to the current ungrounded flow.
- **SC-006**: The system correctly returns entity-type-appropriate content — a company query does not return individual-only guidance and vice versa.

## Assumptions

- The existing knowledge base infrastructure (Pinecone index, scrapers, chunkers, retrieval pipeline, citation verifier) is functional and does not require modification beyond configuration and wiring.
- ATO public content (rulings, legislation, guidance pages) is freely reusable under open government principles.
- The existing `compliance_knowledge` Pinecone namespace is the appropriate target for tax planning content. A new namespace is not required.
- The ATO Legal Database print-friendly URL pattern (`ato.gov.au/law/view/print?DocID={DocID}`) remains stable and accessible.
- Claude (via Anthropic API) can effectively use injected reference material to generate cited responses when instructed to do so in the system prompt.
- The existing cross-encoder reranker model (`ms-marco-MiniLM-L-6-v2`) provides adequate reranking quality for tax planning queries.

## Scope Boundaries

### In Scope
- Wiring the existing RAG retrieval pipeline into the tax planning agent
- Configuring and running existing scrapers to populate tax planning content
- Modifying the agent's system prompt to instruct citation of sources
- Displaying inline citations and a Sources section in chat responses
- Citation verification with confidence indicators
- Entity-type and FY-aware retrieval filtering

### Out of Scope
- Building new scrapers or ingestion infrastructure (existing scrapers are sufficient)
- Modifying the tax calculator or financial computation logic
- Changes to the knowledge base admin UI (existing UI supports all needed operations)
- Ingestion of paid/subscription content (CPA Library, Tax Institute, CCH Master Tax Guide)
- Real-time ATO content change detection or automatic re-ingestion scheduling
- PDF export changes to include citations (can be a follow-up)

## Dependencies

- Spec 045 (Comprehensive Tax Knowledge Base) — the knowledge module infrastructure this feature depends on
- Spec 049 (AI Tax Planning) — the tax planning agent this feature modifies
- Pinecone index `clairo-knowledge` must be initialised and accessible
- Voyage API key must be configured for embedding
- Anthropic API key must be configured for Claude calls
