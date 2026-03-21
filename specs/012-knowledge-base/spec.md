# Feature Specification: Knowledge Base Infrastructure

**Feature Branch**: `012-knowledge-base`
**Created**: 2025-12-29
**Status**: Draft
**Input**: Build foundation for AI-powered compliance and business advisory knowledge

## Overview

The Knowledge Base is the foundation of Clairo's AI moat. It provides:
- Authoritative Australian tax/compliance content (ATO, AustLII, legislation)
- Business advisory content for SMBs, sole traders, and tradespeople
- Rich metadata for filtering by entity type, industry, and relevance
- Foundation for future multi-agent AI system

**Key Research Documents**:
- `RESEARCH.md` - Sources, Qdrant vs pgvector, embedding model selection
- `QUERY-EXAMPLES.md` - MOAT value demonstration
- `CONTEXT-STRATEGY.md` - Tiered context, aggregation tables
- `TENANT-DATA-STRATEGY.md` - PostgreSQL vs Qdrant decisions

---

## User Scenarios & Testing

### User Story 1 - Compliance Knowledge Retrieval (Priority: P1)

As a **system/AI agent**, I need to retrieve relevant Australian tax compliance knowledge so that I can provide accurate, sourced answers to user queries about GST, BAS, PAYG, deductions, and superannuation.

**Why this priority**: This is the core value proposition. Without compliance knowledge, the AI cannot answer tax questions accurately.

**Independent Test**: System can answer "What are the GST thresholds for registration?" with correct ATO-sourced information and citation.

**Acceptance Scenarios**:

1. **Given** the compliance_knowledge collection is populated with ATO content, **When** a query about GST thresholds is made, **Then** the system returns relevant chunks with source citations and effective dates.

2. **Given** a query about sole trader deductions, **When** searching with entity_type filter "sole_trader", **Then** only chunks tagged for sole traders are returned.

3. **Given** a query about PAYG withholding tables, **When** searching for current FY content, **Then** chunks with current effective_date are prioritized over outdated content.

4. **Given** a ruling has been superseded, **When** searching for that topic, **Then** the current ruling is returned, not the superseded one.

---

### User Story 2 - Qdrant Collection Infrastructure (Priority: P1)

As a **developer**, I need Qdrant collections properly configured with vector dimensions, distance metrics, and indexes so that knowledge retrieval is fast and accurate.

**Why this priority**: Infrastructure must exist before content can be ingested. Foundational requirement.

**Independent Test**: Collections can be created, vectors upserted, and similarity search returns results in <100ms.

**Acceptance Scenarios**:

1. **Given** Qdrant is running, **When** the initialization script runs, **Then** 6 collections are created with correct vector configuration (1024 dimensions, cosine distance).

2. **Given** collections exist, **When** vectors are upserted with metadata, **Then** metadata filtering works correctly (entity_types, industries, dates).

3. **Given** 100,000 vectors in a collection, **When** a search is performed with filters, **Then** results are returned in <100ms.

4. **Given** a collection needs recreation, **When** running the reset script, **Then** the collection is dropped and recreated without affecting other collections.

---

### User Story 3 - ATO Content Ingestion Pipeline (Priority: P1)

As an **administrator**, I need to ingest content from ATO RSS feeds and website so that the knowledge base contains current Australian tax compliance information.

**Why this priority**: Without content, the knowledge base is useless. This is the primary content source.

**Independent Test**: Running the ATO ingestion pipeline populates the compliance_knowledge collection with GST, PAYG, super, and BAS content.

**Acceptance Scenarios**:

1. **Given** ATO RSS feed URLs are configured, **When** the RSS ingestion task runs, **Then** new rulings (TR, GSTR, TD, PCG) are fetched, chunked, embedded, and stored.

2. **Given** an ATO webpage URL, **When** the web scraper runs, **Then** content is extracted cleanly (text only, no navigation/boilerplate).

3. **Given** scraped HTML content, **When** processing, **Then** content is chunked at semantic boundaries (headings, paragraphs) not arbitrary character limits.

4. **Given** a chunk of text, **When** embedding with Voyage-3.5-lite, **Then** a 512-dimension vector is generated and stored.

5. **Given** content from different ATO sections, **When** ingested, **Then** appropriate metadata is applied (source_url, source_type, effective_date, entity_types, industries).

---

### User Story 4 - Legislation Content Ingestion (Priority: P2)

As an **administrator**, I need to ingest Australian tax legislation from AustLII so that the knowledge base contains authoritative legal references for ITAA, GST Act, and related legislation.

**Why this priority**: Legislation provides authoritative backing for compliance answers. Important but secondary to ATO guidance which is more practical.

**Independent Test**: ITAA 1997, GST Act sections are searchable and return specific legislative references.

**Acceptance Scenarios**:

1. **Given** AustLII URLs for key Acts, **When** the legislation scraper runs, **Then** section content is extracted with section numbers preserved.

2. **Given** legislation content, **When** chunked, **Then** chunks maintain section references (e.g., "Section 9-5 of GST Act 1999").

3. **Given** legislation metadata, **When** stored, **Then** includes act_name, section_number, and consolidation_date.

---

### User Story 5 - Business Advisory Content Ingestion (Priority: P2)

As an **administrator**, I need to ingest general business advisory content from Business.gov.au, Fair Work, and other sources so that the AI can help business owners with non-tax questions.

**Why this priority**: Expands the AI's value beyond tax to full business advisory. Critical for business owner users but secondary to core compliance.

**Independent Test**: System can answer "How do I register an ABN?" or "What's the minimum wage?" with sourced answers.

**Acceptance Scenarios**:

1. **Given** Business.gov.au content URLs, **When** ingested, **Then** business fundamentals content is stored in business_fundamentals collection.

2. **Given** Fair Work Ombudsman content, **When** ingested, **Then** employment/HR content is stored in people_operations collection with award references.

3. **Given** industry-specific content (trades, retail, hospitality), **When** ingested, **Then** content is stored in industry_knowledge with ANZSIC codes.

---

### User Story 6 - Content Update Pipeline (Priority: P2)

As an **administrator**, I need automated monitoring and updating of content so that the knowledge base stays current without manual intervention.

**Why this priority**: Tax rules change frequently (especially at EOFY). Stale content = wrong answers = liability.

**Independent Test**: New ATO ruling published today is automatically ingested within 24 hours.

**Acceptance Scenarios**:

1. **Given** ATO RSS feeds are monitored, **When** a new ruling is published, **Then** it is detected and queued for ingestion within 4 hours.

2. **Given** a content chunk has changed at source, **When** the update pipeline runs, **Then** the chunk is re-embedded and the old vector is replaced.

3. **Given** content has been superseded, **When** detected, **Then** the superseded flag is set and expiry_date is populated.

4. **Given** update pipeline completes, **When** checked, **Then** a summary log shows: new items added, items updated, items marked superseded.

---

### User Story 7 - Metadata Search and Filtering (Priority: P2)

As a **system/AI agent**, I need to filter knowledge by entity type, industry, date, and source type so that retrieved content is relevant to the specific user context.

**Why this priority**: Personalized answers require filtered retrieval. "Deductions for plumbers" should not return content about medical professionals.

**Independent Test**: Search for "vehicle deductions" with industry="construction" returns only construction-relevant content.

**Acceptance Scenarios**:

1. **Given** chunks tagged with entity_types, **When** searching with filter entity_types=["sole_trader"], **Then** only sole trader relevant content is returned.

2. **Given** chunks tagged with industries, **When** searching with filter industries=["construction"], **Then** construction industry content is prioritized.

3. **Given** chunks with effective_date metadata, **When** searching for current content, **Then** only currently effective content is returned (not future or expired).

4. **Given** multiple matching chunks, **When** sorted by relevance, **Then** higher confidence_level chunks rank higher.

---

### User Story 8 - Embedding Service (Priority: P1)

As a **developer**, I need a reliable embedding service that generates consistent vectors for content and queries so that similarity search works correctly.

**Why this priority**: Embeddings are the core mechanism for retrieval. Must be reliable and consistent.

**Independent Test**: Same text embedded twice produces identical vectors. Query embedding matches semantically similar content.

**Acceptance Scenarios**:

1. **Given** text content, **When** calling the embedding service, **Then** a 1024-dimension vector is returned from Voyage-3.5-lite.

2. **Given** API rate limits, **When** bulk embedding, **Then** requests are batched appropriately and rate limits respected.

3. **Given** embedding API is unavailable, **When** called, **Then** appropriate error is raised with retry guidance.

4. **Given** identical text, **When** embedded multiple times, **Then** identical vectors are produced (deterministic).

---

### User Story 9 - Knowledge Base Admin UI (Priority: P1)

As a **super admin**, I need a web interface to manage knowledge base sources, trigger ingestion jobs, and monitor job progress so that I can maintain the knowledge base without using command-line tools or direct API calls.

**Why this priority**: Essential for operational management. Super admins need visibility and control over the knowledge base without developer intervention.

**Independent Test**: Super admin can log in, view all collections, create a new source, trigger ingestion, and monitor job completion via the UI.

**Acceptance Scenarios**:

1. **Given** the super admin navigates to /admin/knowledge, **When** the page loads, **Then** they see a dashboard with collection health status (6 collections, vector counts, last updated).

2. **Given** the collections dashboard, **When** clicking "Initialize Collections", **Then** all 6 collections are created/verified and status updates in real-time.

3. **Given** the sources tab, **When** the super admin creates a new source (name, type, URL, collection), **Then** the source is saved and appears in the sources list.

4. **Given** a configured source, **When** clicking "Run Ingestion", **Then** an ingestion job is queued and the UI shows job status (pending → running → completed/failed).

5. **Given** a running ingestion job, **When** viewing job details, **Then** the UI displays progress (items processed, added, skipped, failed) updating in real-time or on refresh.

6. **Given** the jobs tab, **When** viewing job history, **Then** the super admin sees recent jobs with status, duration, and statistics.

7. **Given** a completed job with errors, **When** viewing job details, **Then** the error list is displayed with URLs and error messages for troubleshooting.

8. **Given** the search test tab, **When** entering a test query, **Then** the system returns matching chunks with scores, sources, and metadata for verification.

---

### User Story 10 - AI Knowledge Chatbot (Priority: P1)

As a **user**, I need an AI-powered chatbot that answers my Australian tax and business questions using the knowledge base, providing accurate responses with clear citations and source links so that I can trust the information and verify it if needed.

**Why this priority**: This is the user-facing value delivery of the knowledge base. Without a conversational interface, users cannot easily access the knowledge.

**Independent Test**: User asks "What is the GST registration threshold?" and receives a streaming markdown response with the correct answer ($75,000), source citation (ATO), and clickable link to the source page.

**Acceptance Scenarios**:

1. **Given** a user submits a question in the chatbot, **When** the query is processed, **Then** the system retrieves relevant chunks from the knowledge base, generates a response using Claude, and streams it back in markdown format.

2. **Given** the AI generates a response, **When** displaying to the user, **Then** each claim is accompanied by a citation number linking to the source (e.g., [1], [2]).

3. **Given** citations are displayed, **When** the user clicks a citation, **Then** they see the source metadata (title, URL, effective date) and can click through to the original source.

4. **Given** a question with no relevant knowledge base content, **When** the AI responds, **Then** it clearly states that no authoritative source was found and suggests where to find official information.

5. **Given** the response is streaming, **When** displayed, **Then** the user sees text appearing progressively with a typing indicator, providing immediate feedback.

6. **Given** multiple relevant sources exist, **When** generating a response, **Then** the AI synthesizes information from multiple sources and cites each appropriately.

7. **Given** the chatbot interface, **When** viewing conversation history, **Then** previous questions and answers are displayed in a clean chat format.

8. **Given** response metadata, **When** displayed, **Then** shows latency, number of sources consulted, and relevance scores for transparency.

---

### Edge Cases

- What happens when ATO website is down during scraping? → Retry with exponential backoff, log failure, alert if persists >24 hours.
- How does system handle content with no clear effective date? → Default to scrape date, flag for manual review.
- What if embedding API quota is exhausted? → Queue content for later processing, don't fail silently.
- How are duplicate chunks handled? → Hash-based deduplication before embedding.
- What if a ruling is withdrawn (not superseded)? → Mark as withdrawn, remove from active search results.

---

## Requirements

### Functional Requirements

**Infrastructure**:
- **FR-001**: System MUST create and manage 6 Qdrant collections: compliance_knowledge, strategic_advisory, industry_knowledge, business_fundamentals, financial_management, people_operations.
- **FR-002**: System MUST configure collections with 1024-dimension vectors and cosine distance metric.
- **FR-003**: System MUST support payload indexing for metadata fields: entity_types, industries, source_type, effective_date.

**Content Ingestion**:
- **FR-004**: System MUST scrape content from ATO website with rate limiting (max 1 request/second).
- **FR-005**: System MUST parse ATO RSS feeds for new rulings and determinations.
- **FR-006**: System MUST scrape legislation from AustLII with proper attribution.
- **FR-007**: System MUST chunk content at semantic boundaries (headings, paragraphs), not arbitrary character limits.
- **FR-008**: System MUST preserve source attribution (URL, title, date) for all content.

**Embedding**:
- **FR-009**: System MUST use Voyage-3.5-lite for embeddings (1024 dimensions).
- **FR-010**: System MUST batch embedding requests (max 128 texts per request).
- **FR-011**: System MUST handle embedding API errors with retry and exponential backoff.

**Metadata**:
- **FR-012**: System MUST tag content with source_url, source_type, scraped_at.
- **FR-013**: System MUST tag content with effective_date and expiry_date where applicable.
- **FR-014**: System MUST tag content with entity_types (sole_trader, company, trust, partnership).
- **FR-015**: System MUST tag content with industries using ANZSIC codes.
- **FR-016**: System MUST tag rulings with ruling_number (TR, TD, GSTR, PCG format).

**Search**:
- **FR-017**: System MUST support vector similarity search with metadata filtering.
- **FR-018**: System MUST return search results with relevance scores.
- **FR-019**: System MUST support searching multiple collections in parallel.
- **FR-020**: System MUST return results in <100ms for single collection, <200ms for multi-collection.

**Updates**:
- **FR-021**: System MUST check ATO RSS feeds daily for new content.
- **FR-022**: System MUST support re-embedding updated content without duplicating.
- **FR-023**: System MUST log all ingestion activities for troubleshooting.

**Admin UI**:
- **FR-024**: System MUST provide a super admin web interface at /admin/knowledge for knowledge base management.
- **FR-025**: Admin UI MUST display collection health dashboard showing all 6 collections with vector counts and status.
- **FR-026**: Admin UI MUST allow creating, editing, and deleting knowledge sources.
- **FR-027**: Admin UI MUST allow triggering ingestion jobs for individual sources.
- **FR-028**: Admin UI MUST display ingestion job history with status, duration, and statistics.
- **FR-029**: Admin UI MUST show real-time or polling-based progress for running jobs.
- **FR-030**: Admin UI MUST provide a search test interface for verifying retrieval quality.
- **FR-031**: Admin UI MUST require super admin role for access (role-based access control).
- **FR-032**: Admin UI MUST display job errors with source URLs and messages for troubleshooting.

**AI Knowledge Chatbot**:
- **FR-033**: System MUST provide a RAG (Retrieval Augmented Generation) endpoint that accepts user questions and returns AI-generated responses.
- **FR-034**: System MUST stream responses using Server-Sent Events (SSE) for progressive display.
- **FR-035**: System MUST include numbered citations in responses linking to source content.
- **FR-036**: System MUST return source metadata (title, URL, effective_date, relevance_score) with each citation.
- **FR-037**: System MUST use Claude API for response generation with retrieved context.
- **FR-038**: System MUST limit context to top 5-10 most relevant chunks to stay within token limits.
- **FR-039**: System MUST render responses in markdown format with proper headings, lists, and formatting.
- **FR-040**: System MUST provide a user-facing chatbot interface accessible from the main navigation.
- **FR-041**: System MUST display conversation history within the current session.
- **FR-042**: System MUST show loading/typing indicator during streaming responses.
- **FR-043**: System MUST handle cases where no relevant content is found with appropriate messaging.

### Key Entities

- **KnowledgeSource**: Represents a content source (ATO, AustLII, Business.gov.au). Contains: source_id, name, base_url, source_type, scrape_config, last_scraped_at.

- **ContentChunk**: Represents a processed piece of content. Contains: chunk_id, source_id, text, vector_id (Qdrant point ID), metadata (source_url, effective_date, entity_types, industries, etc.), created_at, updated_at.

- **IngestionJob**: Represents a content ingestion run. Contains: job_id, source_id, status (pending, running, completed, failed), started_at, completed_at, items_processed, items_added, items_updated, errors.

- **QdrantCollection**: Represents a knowledge collection. Contains: collection_name, description, vector_config, payload_indexes, created_at.

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: No - knowledge base is internal, no user auth.
- [x] **Data Access Events**: Yes - log all knowledge retrieval for quality monitoring.
- [x] **Data Modification Events**: Yes - log all content ingestion and updates.
- [x] **Integration Events**: Yes - log all external API calls (ATO, AustLII, Voyage).
- [ ] **Compliance Events**: No - this is the source of compliance knowledge, not compliance actions.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| knowledge.search | Search query executed | query_text, collections_searched, result_count, latency_ms | 90 days | None |
| knowledge.ingestion.started | Ingestion job begins | job_id, source_id, source_type | 1 year | None |
| knowledge.ingestion.completed | Ingestion job finishes | job_id, items_processed, items_added, items_updated, errors | 1 year | None |
| knowledge.embedding.called | Voyage API called | text_count, tokens_used, latency_ms | 90 days | None |
| knowledge.source.scraped | External source scraped | source_url, status_code, content_length | 90 days | None |

### Compliance Considerations

- **ATO Requirements**: Content sourced from ATO must preserve attribution and not misrepresent guidance.
- **Data Retention**: Knowledge base content can be updated/replaced as sources change. Audit logs retained per above.
- **Access Logging**: Internal system - no user-level access logging required at this layer.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 6 Qdrant collections created and operational within 24 hours of deployment.
- **SC-002**: Minimum 50,000 content chunks ingested from ATO and legislation sources.
- **SC-003**: Search latency <100ms for single collection, <200ms for multi-collection (p95).
- **SC-004**: Embedding pipeline processes 1,000 chunks in <5 minutes.
- **SC-005**: Daily RSS monitoring detects new ATO content within 4 hours of publication.
- **SC-006**: Content retrieval accuracy >90% (measured by manual review of sample queries).
- **SC-007**: Zero unhandled errors in ingestion pipeline over 7-day period.
- **SC-008**: Admin UI loads collection dashboard in <2 seconds.
- **SC-009**: Super admin can trigger and monitor ingestion job end-to-end via UI.
- **SC-010**: Job progress updates displayed within 5 seconds of status change.

---

## Technical Constraints

Based on research decisions:

| Constraint | Decision | Rationale |
|------------|----------|-----------|
| Vector Database | Qdrant (not pgvector) | Already in stack, excellent metadata filtering, multi-tenancy support |
| Embedding Model | Voyage-3.5-lite (1024d) | Best RAG accuracy/cost, trained on "tricky negatives" for legal text |
| Embedding Dimensions | 1024 | Default output dimensions for voyage-3.5-lite |
| Chunking Strategy | Semantic (headings/paragraphs) | Preserves meaning better than character splits |
| Rate Limiting | 1 req/sec for ATO, respect robots.txt | Ethical scraping, avoid blocks |
| Admin UI Access | Super admin role only | Knowledge base management is sensitive, requires elevated permissions |

---

## Out of Scope (Phase D)

The following are explicitly NOT part of Spec 012:

- Per-tenant document collections (Spec 021: Document Upload)
- RAG query pipeline and LLM integration (Spec 013: Compliance RAG Engine)
- Multi-agent routing (Spec 014: Multi-Agent Framework)
- AI context aggregation tables (will be added as needed in later specs)
- User-facing chat interface (Spec 015: Accountant AI Assistant)

---

## Dependencies

- **Qdrant**: Already running in docker-compose on port 6333
- **Voyage AI API**: Requires API key in environment
- **ATO Website**: Public access, must respect rate limits
- **AustLII**: Public access, use legaldata package where helpful
- **Celery**: For background ingestion jobs
- **Frontend (Next.js)**: For admin UI at /admin/knowledge
- **Clerk Auth**: For super admin role verification
