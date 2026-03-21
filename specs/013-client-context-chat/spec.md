# Requirements Document: Client-Context Chat

## Introduction

This document defines the requirements for enabling client-specific context in the AI Knowledge Assistant chat. Building upon the existing Knowledge Base (Spec 012) and Xero Data Sync (Spec 004), this feature allows accountants to select a client from their synced Xero data and have the AI assistant answer questions in the context of that specific client's financial situation.

**Client-Context Chat is a key differentiator (MOAT) for Clairo.** It transforms the AI from a generic tax knowledge assistant into a personalized advisor that understands each client's unique financial position, enabling accountants to provide faster, more accurate, and more tailored advice.

---

## ⚠️ TERMINOLOGY CLARIFICATION (Implementation Note)

**In Clairo, "Client" = Xero Organization (XeroConnection), NOT Xero Contact.**

| Term | Database Model | Description | Example |
|------|---------------|-------------|---------|
| **Client** | `XeroConnection` | The accountant's client business/organization | "KR8 IT Pty Ltd", "ACME Corp" |
| **Contact** | `XeroClient` | A contact WITHIN a client's Xero organization | "7 Eleven" (supplier), "John Smith" (customer) |

**Why this matters:**
- Financial data (invoices, transactions, GST) belongs to the **organization**, not individual contacts
- When an accountant asks "What's the GST liability for KR8 IT?", they want organization-level data
- Aggregation tables should be keyed by `connection_id` (organization), not `client_id` (contact)
- The `/clients` page shows `XeroConnection` records (organizations), not `XeroClient` records (contacts)

**Data Model Relationships:**
```
XeroConnection (Organization)     ← This is the "Client"
  └── XeroClient (Contacts)       ← Customers/Suppliers within the organization
  └── XeroInvoice (Invoices)      ← Financial data linked via connection_id
  └── XeroBankTransaction         ← Financial data linked via connection_id
```

---

**Key Context:**
- Knowledge Base infrastructure exists with Qdrant collections and AI chatbot (Spec 012 complete)
- Xero sync provides organizations, contacts, invoices, bank transactions, and accounts (Spec 004 complete)
- Technical approach: PostgreSQL structured data as context injection (NOT per-client vectors)
- At query time, relevant client data is fetched from PostgreSQL and injected into the LLM prompt
- Tiered context strategy: Profile (always) + Query-relevant summaries + On-demand detail

**Example Use Cases:**
1. "How is my client ACME doing in terms of cash flow?" - Uses organization's bank transactions and AR/AP aging
2. "What is the GST liability for Q1 for client XYZ?" - Aggregates organization invoices and calculates GST
3. "Are there any overdue invoices for Smith & Co?" - Queries organization invoices by due date
4. "What expenses can we claim for the client's vehicle?" - Combines organization context with knowledge base

---

## Requirements

### Requirement 1: Client Selector Interface

**User Story:** As an accountant, I want to select a client (Xero organization) from my synced Xero connections in the chat interface, so that I can ask questions about that specific client's financial situation.

#### Acceptance Criteria

1. WHEN the user accesses the AI Knowledge Assistant chat THEN the system SHALL display a client selector dropdown/search component in the chat header.

2. WHEN the user types in the client selector THEN the system SHALL search across synced Xero organizations (`XeroConnection.organization_name`) by name, displaying matching results with typeahead suggestions.

3. WHEN the user selects a client from the selector THEN the system SHALL enter "client context mode" and display a visual indicator showing the selected organization's name.

4. WHEN in client context mode THEN the system SHALL display a clear visual distinction (e.g., colored header, client badge) differentiating it from general knowledge chat mode.

5. WHEN a client is selected THEN the system SHALL display basic organization information (name, GST status if available) in the chat header for confirmation.

6. WHEN the user clicks a "clear" or "remove client" action THEN the system SHALL return to general knowledge chat mode and remove the client context indicator.

7. IF the user has no synced Xero connections THEN the system SHALL display a message indicating that client context requires a connected Xero organization.

8. WHEN searching clients THEN the system SHALL only return Xero connections (`XeroConnection`) belonging to the current tenant (RLS enforced).

---

### Requirement 2: Client Context Building

**User Story:** As an accountant, I want the AI to automatically understand my selected client's financial situation, so that I can ask questions without manually providing background information.

#### Acceptance Criteria

1. WHEN a client is selected and the user submits a question THEN the system SHALL fetch the client's profile data from PostgreSQL including: organization name, ABN, entity type, industry code, GST registration status, revenue bracket, and employee count.

2. WHEN building client context THEN the system SHALL detect the query intent (tax/deductions, cash flow, GST/BAS, compliance, general) and include only summaries relevant to that intent.

3. WHEN the query intent is TAX/DEDUCTIONS THEN the system SHALL include: expense summary by category, deduction analysis (if available), asset summary, and prior year comparison.

4. WHEN the query intent is CASH_FLOW THEN the system SHALL include: accounts receivable aging, accounts payable aging, monthly cash flow trends, and top debtors list.

5. WHEN the query intent is GST/BAS THEN the system SHALL include: current period GST summary (1A, 1B, net), prior quarters comparison, and any adjustment items.

6. WHEN the query intent is COMPLIANCE THEN the system SHALL include: contractor payment summary, payroll summary, superannuation summary, and lodgement history.

7. WHEN building context THEN the system SHALL respect a token budget of approximately 4,000-12,500 tokens for client context to maintain cost efficiency and avoid context window limits.

8. IF aggregated summaries are not yet computed for the client THEN the system SHALL fall back to generating basic aggregations from raw data on-demand.

---

### Requirement 3: Context-Aware AI Responses

**User Story:** As an accountant, I want the AI to combine my client's specific financial data with general tax knowledge, so that I receive personalized and accurate advice.

#### Acceptance Criteria

1. WHEN a question is submitted in client context mode THEN the system SHALL inject the client context into the LLM prompt alongside the RAG-retrieved knowledge base content.

2. WHEN generating a response THEN the system SHALL reference specific client data (amounts, dates, names) when relevant to the question.

3. WHEN the AI response includes claims about tax rules or regulations THEN the system SHALL cite the knowledge base sources as per existing citation requirements.

4. WHEN the AI response includes client-specific calculations THEN the system SHALL show the calculation methodology and underlying data.

5. IF the question requires data not available in the current context summaries THEN the system SHALL either request additional information from the user OR perform an on-demand query for specific detail (Tier 3 context).

6. WHEN no relevant knowledge base content is found for the tax/compliance aspect of a question THEN the system SHALL clearly state this while still providing client-specific data insights.

7. WHEN responding about client data THEN the system SHALL include the data freshness indicator (last sync timestamp) so the accountant knows how current the information is.

---

### Requirement 4: Client Financial Data Aggregation

**User Story:** As a system, I need to pre-compute organization-level financial summaries from synced Xero data, so that context can be efficiently injected into AI queries without excessive computation or token usage.

#### Acceptance Criteria

1. WHEN a Xero sync completes for a connection THEN the system SHALL compute and store aggregated summaries at the **organization level** (keyed by `connection_id`).

2. WHEN computing expense summaries THEN the system SHALL aggregate all transactions for the organization by account code and category, calculating totals, transaction counts, and GST amounts for configurable periods (month, quarter, year).

3. WHEN computing accounts receivable aging THEN the system SHALL calculate amounts in aging buckets (current, 31-60 days, 61-90 days, over 90 days) and identify top debtors across the organization.

4. WHEN computing GST period summaries THEN the system SHALL calculate GST on sales (1A), GST on purchases (1B), and net GST position for each BAS period for the organization.

5. WHEN computing monthly trends THEN the system SHALL store revenue, expenses, gross profit, net profit, and cash flow metrics for each month for the organization.

6. IF an organization has no transactions in a period THEN the system SHALL store zero values rather than omitting the record, to indicate data completeness.

7. WHEN aggregations are computed THEN the system SHALL store the computation timestamp for cache invalidation and freshness indication.

8. WHEN querying aggregations THEN the system SHALL enforce tenant isolation via RLS policies on all aggregation tables.

**Implementation Note:** All aggregation tables should use `connection_id` (FK to `xero_connections`) as the primary grouping key, NOT `client_id` (FK to `xero_clients`). Financial data belongs to the organization.

---

### Requirement 5: Client Context Mode Persistence

**User Story:** As an accountant, I want my client selection to persist throughout my chat session, so that I can ask multiple questions about the same client without reselecting them.

#### Acceptance Criteria

1. WHEN a client is selected THEN the system SHALL maintain that selection for all subsequent messages in the current chat session.

2. WHEN the user starts a new chat/conversation THEN the system SHALL clear the previous client selection and default to general knowledge mode.

3. WHEN the user explicitly clears the client selection THEN the system SHALL return to general knowledge mode for subsequent messages.

4. WHEN the user selects a different client THEN the system SHALL switch context to the new client and display a system message indicating the context switch.

5. WHEN viewing conversation history THEN the system SHALL display which client (if any) was selected for each message in the conversation.

6. IF the browser tab is refreshed or restored THEN the system SHOULD restore the previously selected client context if the user returns within a reasonable session window.

---

### Requirement 6: Multi-Turn Conversations with Drill-Down

**User Story:** As an accountant, I want to ask follow-up questions that drill into specific details of my client's data, so that I can investigate anomalies or get more granular information.

#### Acceptance Criteria

1. WHEN the user asks a follow-up question requesting more detail THEN the system SHALL fetch additional data from PostgreSQL (Tier 3 on-demand context) for the specific area of inquiry.

2. WHEN the user asks about specific transactions (e.g., "Show me the overdue invoices") THEN the system SHALL fetch and include individual transaction records in the response.

3. WHEN the user asks about a specific time period THEN the system SHALL constrain data retrieval to that period and adjust summaries accordingly.

4. WHEN drilling into detail THEN the system SHALL respect a Tier 3 token budget of approximately 500-5,000 tokens for raw data.

5. IF the requested detail would exceed context limits THEN the system SHALL summarize or paginate the data, offering to show more specific subsets.

6. WHEN raw transaction data is included in context THEN the system SHALL format it in a structured, readable manner (tables or lists) for the AI to reference.

---

### Requirement 7: Client Context with Knowledge Base Integration

**User Story:** As an accountant, I want to ask questions that combine my client's specific situation with ATO regulations and tax knowledge, so that I receive tailored compliance advice.

#### Acceptance Criteria

1. WHEN a question involves both client data and compliance rules THEN the system SHALL retrieve relevant chunks from the Qdrant knowledge base AND inject client context from PostgreSQL.

2. WHEN the AI generates a response THEN the system SHALL clearly distinguish between client-specific data and authoritative knowledge base content.

3. WHEN answering industry-specific questions THEN the system SHALL use the client's industry code to filter knowledge base results for relevance.

4. WHEN answering entity-type-specific questions THEN the system SHALL use the client's entity type (sole trader, company, trust) to filter knowledge base results.

5. WHEN displaying the response THEN the system SHALL provide citations for knowledge base sources separately from client data references.

6. IF the client's data suggests a compliance issue THEN the system SHALL retrieve and cite relevant ATO guidance on the topic.

---

### Requirement 8: Data Privacy and Access Control

**User Story:** As an accountant, I want client data to be securely isolated and only accessible to authorized users in my practice, so that client confidentiality is maintained.

#### Acceptance Criteria

1. WHEN fetching client context THEN the system SHALL enforce tenant isolation via RLS, ensuring users can only access clients from their own tenant.

2. WHEN fetching client data THEN the system SHALL verify the client belongs to a Xero connection owned by the user's tenant.

3. WHEN client context is injected into the LLM prompt THEN the system SHALL NOT log sensitive financial data (amounts, ABN, client names) to application logs.

4. WHEN audit events are recorded for client context queries THEN the system SHALL log the connection_id and query intent but NOT the full financial context.

5. IF a user attempts to access a client outside their tenant THEN the system SHALL reject the request and log a security audit event.

6. WHEN storing conversation history THEN the system SHALL associate conversations with tenant_id and enforce RLS for retrieval.

---

### Requirement 9: Performance and Caching

**User Story:** As an accountant, I want client context to be available quickly, so that I can have a responsive conversation without waiting for data to load.

#### Acceptance Criteria

1. WHEN a client is selected THEN the system SHALL retrieve the client profile and basic context in under 500ms (p95).

2. WHEN building query-specific context THEN the system SHALL retrieve aggregated summaries in under 1 second (p95) from pre-computed tables.

3. WHEN pre-computed aggregations exist THEN the system SHALL use them preferentially over computing aggregations on-demand.

4. IF aggregations are stale (older than configurable threshold, e.g., 24 hours) THEN the system SHALL display a freshness warning to the user.

5. WHEN a Xero sync completes THEN the system SHALL invalidate and refresh affected aggregation caches.

6. WHEN the same client context is requested multiple times in a session THEN the system SHALL cache the profile data to avoid redundant database queries.

---

### Requirement 10: Error Handling and Edge Cases

**User Story:** As an accountant, I want clear feedback when client data is incomplete or unavailable, so that I understand the limitations of the AI's responses.

#### Acceptance Criteria

1. IF the selected client has no synced financial data THEN the system SHALL display a message indicating that data is not yet available and suggest triggering a Xero sync.

2. IF the Xero connection for a client is in NEEDS_REAUTH status THEN the system SHALL display a warning that data may be stale and prompt re-authorization.

3. IF aggregation computation fails THEN the system SHALL fall back to a degraded response with available data and log the error for investigation.

4. WHEN data is missing for a specific query type THEN the system SHALL inform the user which data is unavailable (e.g., "No invoice data found for this client").

5. IF the AI cannot answer a question due to insufficient context THEN the system SHALL explain what additional information would be needed.

6. WHEN the user asks about a date range outside available data THEN the system SHALL indicate the available data range and offer to answer for that period instead.

---

## Non-Functional Requirements

### Performance

1. WHEN building client context THEN the system SHALL complete in under 2 seconds for the full context build (profile + summaries).

2. WHEN responding to a client-context query THEN the total end-to-end latency (context build + RAG retrieval + LLM generation) SHALL be under 10 seconds (p95).

3. WHEN computing aggregations during Xero sync THEN the system SHALL not add more than 30% overhead to the sync job duration.

### Scalability

1. WHEN a tenant has many clients (1000+) THEN the client selector search SHALL remain responsive with sub-second results.

2. WHEN aggregation tables grow THEN the system SHALL use appropriate indexes to maintain query performance.

3. WHEN multiple users query client context simultaneously THEN the system SHALL handle concurrent access without degradation.

### Reliability

1. WHEN aggregation computation fails for a client THEN the system SHALL not block the overall Xero sync job.

2. WHEN the knowledge base is unavailable THEN the system SHALL still provide client data insights with appropriate messaging.

3. WHEN context building encounters partial failures THEN the system SHALL provide a degraded but functional response.

### Security

1. WHEN client data is transmitted THEN the system SHALL use HTTPS/TLS encryption.

2. WHEN storing client context in session THEN the system SHALL NOT persist sensitive data to browser localStorage.

3. WHEN AI responses contain client data THEN the system SHALL apply the same access controls as direct data access.

### Observability

1. WHEN client context queries are executed THEN the system SHALL log: connection_id, query_intent, context_tokens, latency_ms, success/failure.

2. WHEN context building fails THEN the system SHALL log detailed error information for troubleshooting.

3. WHEN measuring AI response quality THEN the system SHALL track queries with and without client context separately.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Per-client vector embeddings** - Decision made to use PostgreSQL aggregations, not Qdrant per-client collections
2. **Client document upload** - Separate spec (Spec 021: Document Upload)
3. **AI-generated client reports** - Future enhancement
4. **Multi-client comparison queries** - "Compare ACME to XYZ" style queries
5. **Automated insights/alerts** - Proactive AI suggestions without user query
6. **Write-back to Xero** - Modifying client data through the AI chat
7. **Voice/audio chat interface** - Text-based only

---

## Dependencies

| Dependency | Description | Status |
|------------|-------------|--------|
| Spec 004: Xero Data Sync | Client contacts, invoices, transactions, accounts synced | COMPLETE |
| Spec 012: Knowledge Base | Qdrant collections, AI chatbot, RAG pipeline | COMPLETE |
| Aggregation Tables | PostgreSQL tables for pre-computed summaries | TO BE CREATED |
| Client Profile Table | client_ai_profile for context Tier 1 | TO BE CREATED |

---

## Glossary

| Term | Definition |
|------|------------|
| **Client Context Mode** | Chat mode where AI responses incorporate specific client financial data |
| **General Knowledge Mode** | Chat mode for general tax/compliance questions without client-specific data |
| **Context Injection** | Adding structured data to LLM prompt as context for personalized responses |
| **Tiered Context** | Strategy with 3 tiers: Profile (always), Query-relevant summaries, On-demand detail |
| **Query Intent** | Detected category of user question (tax, cash flow, GST, compliance, general) |
| **Aggregation Tables** | Pre-computed summary tables for efficient context retrieval |
| **RAG** | Retrieval Augmented Generation - combining retrieved knowledge with LLM generation |

