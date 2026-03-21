# Implementation Plan: Client-Context Chat (Spec 013)

This document outlines the implementation tasks for adding client-specific context to the AI Knowledge Assistant chat. The feature enables accountants to select a client and have the AI answer questions with personalized financial insights.

---

## Phase 1: Foundation (Data Models + Migrations)

- [x] 1. Create aggregation data models
  - [x] 1.1 Create `ClientAIProfile` model in `backend/app/modules/knowledge/aggregation_models.py`
    - Define fields: `tenant_id`, `client_id`, `connection_id`, `entity_type`, `industry_code`, `gst_registered`, `revenue_bracket`, `employee_count`, `computed_at`
    - Add foreign key relationships to `tenants`, `xero_clients`, `xero_connections`
    - Include `TimestampMixin` for `created_at`/`updated_at`
    - Add index on `tenant_id` for RLS performance
    - _Requirements: 2.1 (client profile data), 8.1 (tenant isolation)_

  - [x] 1.2 Create `ClientExpenseSummary` model
    - Define fields: `tenant_id`, `client_id`, `period_type`, `period_start`, `period_end`, `by_account_code` (JSONB), `by_category` (JSONB), `total_expenses`, `total_gst`, `transaction_count`, `computed_at`
    - Add unique constraint on (`client_id`, `period_type`, `period_start`)
    - Add composite index on (`client_id`, `period_start`)
    - _Requirements: 4.2 (expense summary by category)_

  - [x] 1.3 Create `ClientARAgingSummary` model
    - Define aging bucket fields: `current_amount`, `days_31_60`, `days_61_90`, `over_90_days`, `total_outstanding`
    - Add `top_debtors` JSONB field for storing debtor list
    - Add unique constraint on (`client_id`, `as_of_date`)
    - _Requirements: 4.3 (AR aging buckets)_

  - [x] 1.4 Create `ClientAPAgingSummary` model
    - Mirror AR aging structure with AP-specific fields
    - Add `top_creditors` JSONB field
    - _Requirements: 2.4 (accounts payable aging for cash flow intent)_

  - [x] 1.5 Create `ClientGSTSummary` model
    - Define BAS-specific fields: `gst_on_sales_1a`, `gst_on_purchases_1b`, `net_gst`, `total_sales`, `total_purchases`
    - Add `adjustments` JSONB for flexibility
    - Add unique constraint on (`client_id`, `period_type`, `period_start`)
    - _Requirements: 4.4 (GST period summaries)_

  - [x] 1.6 Create `ClientMonthlyTrend` model
    - Define trend fields: `year`, `month`, `revenue`, `expenses`, `gross_profit`, `net_cashflow`
    - Add unique constraint on (`client_id`, `year`, `month`)
    - _Requirements: 4.5 (monthly financial trends)_

  - [x] 1.7 Create `ClientComplianceSummary` model
    - Define compliance fields: `total_wages`, `total_payg_withheld`, `total_super`, `employee_count`, `contractor_payments`, `contractor_count`
    - Add unique constraint on (`client_id`, `period_type`, `period_start`)
    - _Requirements: 2.6 (compliance intent summaries)_

- [x] 2. Create database migration for aggregation tables
  - [x] 2.1 Generate Alembic migration file
    - Create all aggregation tables with proper column types
    - Add all indexes and constraints defined in models
    - _Requirements: 4.1 (store aggregated summaries)_
    - **Note**: Created migrations 012, 013, 014, 015 for aggregation tables and fixes

  - [x] 2.2 Add RLS policies to new tables
    - Create RLS policy for each aggregation table enforcing `tenant_id` filtering
    - Use `app.current_tenant_id` session variable pattern from existing tables
    - _Requirements: 4.8 (RLS on aggregation tables), 8.1-8.2 (tenant isolation)_

  - [ ] 2.3 Write unit tests for model creation
    - Test model instantiation with valid data
    - Test constraint violations (uniqueness, foreign keys)
    - Test JSONB field serialization/deserialization
    - _Requirements: Ensure data model correctness_

---

## Phase 2: Aggregation Service

- [x] 3. Create aggregation repository layer
  - [x] 3.1 Create `AggregationRepository` class in `backend/app/modules/knowledge/aggregation_repository.py`
    - Implement `get_client_profile(client_id, tenant_id)` method
    - Implement `get_expense_summary(client_id, period_type, period_start)` method
    - Implement `get_ar_aging(client_id, as_of_date)` method
    - Implement `get_ap_aging(client_id, as_of_date)` method
    - Implement `get_gst_summary(client_id, period_type, period_start)` method
    - Implement `get_monthly_trends(client_id, months)` method
    - Implement `get_compliance_summary(client_id, period_type, period_start)` method
    - Add upsert methods for each summary type
    - **Note**: All methods use `connection_id` (org level) not `client_id` (contact level)
    - _Requirements: 4.1-4.8, 9.2 (efficient retrieval)_

  - [ ] 3.2 Write unit tests for repository methods
    - Test each getter returns correct data
    - Test upsert creates new records correctly
    - Test upsert updates existing records correctly
    - Test tenant isolation is enforced
    - _Requirements: 8.1-8.2 (tenant isolation verification)_

- [x] 4. Implement aggregation computation service
  - [x] 4.1 Create `AggregationService` class in `backend/app/modules/knowledge/aggregation_service.py`
    - Inject `AsyncSession` and `AggregationRepository`
    - Implement `compute_all_for_connection(connection_id)` method
    - **Note**: Computes at organization level (connection_id), not per-contact
    - _Requirements: 4.1 (compute on sync completion)_

  - [x] 4.2 Implement `compute_expense_summary()` method
    - Query `XeroBankTransaction` and `XeroInvoice` for expense data
    - Aggregate by account code using SQL GROUP BY
    - Map account codes to categories using `XeroAccount` data
    - Calculate totals for configurable periods (month, quarter, year)
    - _Requirements: 4.2 (expense aggregation by category)_

  - [x] 4.3 Implement `compute_ar_aging()` method
    - Query `XeroInvoice` where `invoice_type == ACCREC` and unpaid
    - Calculate days overdue from `due_date`
    - Bucket amounts into current/31-60/61-90/90+ categories
    - Identify top 5 debtors by amount owed
    - _Requirements: 4.3 (AR aging buckets), 2.4 (top debtors)_

  - [x] 4.4 Implement `compute_ap_aging()` method
    - Query `XeroInvoice` where `invoice_type == ACCPAY` and unpaid
    - Apply same bucketing logic as AR
    - Identify top 5 creditors
    - _Requirements: 2.4 (AP aging for cash flow)_

  - [x] 4.5 Implement `compute_gst_summary()` method
    - Query invoices and transactions for GST amounts
    - Calculate 1A (GST on sales) from ACCREC invoices
    - Calculate 1B (GST on purchases) from ACCPAY invoices and bank transactions
    - Calculate net GST position
    - Support both monthly and quarterly period types
    - _Requirements: 4.4 (GST summary for BAS periods)_

  - [x] 4.6 Implement `compute_monthly_trends()` method
    - Query revenue from ACCREC invoices by month
    - Query expenses from ACCPAY invoices and bank transactions by month
    - Calculate gross profit (revenue - cost of goods)
    - Calculate net cashflow from bank transactions
    - Store last 12 months of data
    - _Requirements: 4.5 (monthly trend metrics)_

  - [x] 4.7 Implement `compute_compliance_summary()` method
    - Query `XeroPayRun` for PAYG and super totals
    - Aggregate wages and withholding by quarter/year
    - Count employees from posted pay runs
    - Calculate contractor payments (if identifiable from transactions)
    - _Requirements: 2.6 (compliance summary for PAYG, super, contractors)_

  - [x] 4.8 Implement `compute_client_profile()` method
    - Determine `revenue_bracket` from total annual revenue
    - Count employees from `XeroEmployee` or `XeroPayRun`
    - Infer `gst_registered` from presence of GST in transactions
    - Leave `entity_type` and `industry_code` as null (future enhancement)
    - **Note**: Also syncs entity_type from Xero Organisation API
    - _Requirements: 2.1 (client profile data)_

  - [ ] 4.9 Write comprehensive unit tests for aggregation service
    - Test expense summary calculation with sample data
    - Test AR/AP aging bucketing logic
    - Test GST calculation accuracy
    - Test monthly trend aggregation
    - Test compliance summary with payroll data
    - Test handling of clients with no data (store zeros)
    - _Requirements: 4.6 (store zeros for no-data periods)_

- [x] 5. Create aggregation Celery task
  - [x] 5.1 Create `compute_aggregations_task` in `backend/app/tasks/aggregation.py`
    - Accept `connection_id` as parameter
    - Instantiate `AggregationService` with database session
    - Call `compute_all_for_connection()`
    - Log computation statistics and timing
    - Handle exceptions gracefully without failing the parent sync job
    - _Requirements: 4.1 (compute on sync), NFR Reliability (don't block sync)_

  - [x] 5.2 Integrate task with Xero sync completion
    - Modify existing sync job completion handler to trigger aggregation task
    - Use Celery chain or callback pattern for async execution
    - Ensure aggregation runs after sync data is committed
    - **Note**: Added to `backend/app/tasks/__init__.py` for task registration
    - _Requirements: 4.1 (trigger on sync complete), 9.5 (invalidate on sync)_

  - [ ] 5.3 Write integration tests for aggregation task
    - Test task execution completes successfully
    - Test task handles missing connection gracefully
    - Test aggregation data is persisted after task completes
    - Test task timing meets NFR (< 30% sync overhead)
    - _Requirements: NFR Performance (sync overhead)_

---

## Phase 3: Context Building Service

- [x] 6. Implement query intent detection
  - [x] 6.1 Create `QueryIntent` enum in `backend/app/modules/knowledge/intent_detector.py`
    - Define values: `TAX_DEDUCTIONS`, `CASH_FLOW`, `GST_BAS`, `COMPLIANCE`, `GENERAL`
    - _Requirements: 2.2 (detect query intent)_

  - [x] 6.2 Implement `QueryIntentDetector` class
    - Define keyword patterns for each intent category
    - Implement `detect(query, conversation_history)` method
    - Score each intent based on keyword matches
    - Consider conversation history for follow-up context
    - Default to `GENERAL` if no clear match
    - _Requirements: 2.2-2.6 (intent-based context selection)_

  - [ ] 6.3 Write unit tests for intent detection
    - Test GST-related queries return `GST_BAS` intent
    - Test cash flow queries return `CASH_FLOW` intent
    - Test tax/deduction queries return `TAX_DEDUCTIONS` intent
    - Test compliance queries return `COMPLIANCE` intent
    - Test ambiguous queries return `GENERAL` intent
    - Test conversation context influences detection
    - _Requirements: 2.2-2.6 (accurate intent detection)_

- [x] 7. Implement token budget management
  - [x] 7.1 Create `TokenBudget` dataclass in `backend/app/modules/knowledge/token_budget.py`
    - Define tier budgets: `tier1_profile=500`, `tier2_summaries=4000`, `tier3_details=2000`, `rag_context=2000`
    - Define `total_max=12500`
    - _Requirements: 2.7 (token budget management)_

  - [x] 7.2 Implement `TokenBudgetManager` class
    - Implement `estimate_tokens(text)` using chars/4 approximation
    - Implement `fits_budget(text, tier)` check
    - Implement `truncate_to_budget(text, tier)` for overflow
    - Implement `allocate_remaining(used)` for budget reallocation
    - _Requirements: 2.7 (respect token limits), 6.4-6.5 (Tier 3 limits)_

  - [ ] 7.3 Write unit tests for token budget manager
    - Test token estimation accuracy
    - Test budget checking for each tier
    - Test truncation produces valid output
    - Test budget reallocation logic
    - _Requirements: 2.7 (token budget correctness)_

- [x] 8. Implement context builder service
  - [x] 8.1 Create `ClientContext` dataclass in `backend/app/modules/knowledge/context_builder.py`
    - Define fields: `client_id`, `profile`, `query_intent`, `summaries`, `raw_data`, `token_count`, `data_freshness`
    - _Requirements: 2.1-2.7 (context structure)_

  - [x] 8.2 Create `ClientProfile` dataclass
    - Define fields: `id`, `name`, `abn`, `entity_type`, `industry_code`, `gst_registered`, `revenue_bracket`, `employee_count`, `connection_id`, `last_sync_at`
    - _Requirements: 2.1 (profile fields)_

  - [x] 8.3 Implement `ContextBuilderService` class
    - Inject `AggregationRepository`, `XeroRepository`, `QueryIntentDetector`, `TokenBudgetManager`
    - Implement constructor with dependency injection
    - _Requirements: Context building orchestration_

  - [x] 8.4 Implement `get_tier1_profile()` method
    - Fetch `ClientAIProfile` from repository
    - Fall back to basic `XeroClient` data if profile not computed
    - Return `ClientProfile` dataclass
    - _Requirements: 2.1 (always include profile)_

  - [x] 8.5 Implement `get_tier2_summaries()` method
    - Switch on `QueryIntent` to determine relevant summaries
    - For `TAX_DEDUCTIONS`: fetch expense summary, monthly trends
    - For `CASH_FLOW`: fetch AR aging, AP aging, monthly trends
    - For `GST_BAS`: fetch GST summary, prior quarters
    - For `COMPLIANCE`: fetch compliance summary
    - For `GENERAL`: fetch basic profile only
    - Apply token budget to summary content
    - _Requirements: 2.3-2.6 (intent-specific summaries)_

  - [x] 8.6 Implement `get_tier3_details()` method
    - Detect drill-down requests from query
    - Fetch raw invoice/transaction data from Xero tables
    - Apply Tier 3 token budget (500-5000 tokens)
    - Format data as structured list
    - _Requirements: 6.1-6.6 (on-demand detail retrieval)_

  - [x] 8.7 Implement `build_context()` method
    - Orchestrate Tier 1 + Tier 2 + optional Tier 3
    - Track total token count
    - Return `ClientContext` with freshness timestamp
    - _Requirements: 2.1-2.7 (complete context building)_

  - [x] 8.8 Implement `format_context_for_prompt()` method
    - Format profile as structured text block
    - Format summaries in human-readable format
    - Format raw data as markdown tables/lists
    - Include data freshness note
    - _Requirements: 3.2 (reference specific client data)_

  - [ ] 8.9 Write comprehensive unit tests for context builder
    - Test Tier 1 profile fetching
    - Test Tier 2 summary selection by intent
    - Test Tier 3 detail retrieval
    - Test full context build orchestration
    - Test prompt formatting output
    - Test fallback behavior when data missing
    - _Requirements: 2.8 (fallback for missing data)_

---

## Phase 4: Chat Integration

- [x] 9. Implement client context chatbot
  - [x] 9.1 Create `ClientContextChatbot` class in `backend/app/modules/knowledge/client_chatbot.py`
    - Inject `KnowledgeChatbot`, `ContextBuilderService`, `AnthropicSettings`
    - Store Anthropic client reference
    - _Requirements: 3.1 (combine client context with RAG)_

  - [x] 9.2 Implement `search_clients()` method
    - Query `XeroConnection` table with ILIKE search on organization name
    - Filter by tenant_id for RLS enforcement
    - Return list of `ClientSearchResult` with connection info
    - **Note**: Searches XeroConnection (orgs), not XeroClient (contacts)
    - _Requirements: 1.2 (typeahead client search), 1.8 (RLS enforced)_

  - [x] 9.3 Implement enhanced system prompt
    - Extend `SYSTEM_PROMPT` with client context instructions
    - Include guidance for citing client data vs knowledge base
    - Add data freshness note template
    - _Requirements: 3.2-3.7 (response generation rules)_

  - [x] 9.4 Implement `chat_with_client_context()` method
    - Build client context using `ContextBuilderService`
    - Retrieve RAG context using existing `KnowledgeChatbot.retrieve_context()`
    - Combine client context + RAG context in prompt
    - Stream response using Anthropic API
    - Return response generator and metadata
    - _Requirements: 3.1 (inject context), 7.1-7.5 (KB integration)_

  - [x] 9.5 Implement metadata extraction
    - Parse response for client data references
    - Track context token count
    - Build `ClientChatMetadata` with citations
    - _Requirements: 3.4 (show calculation methodology)_

  - [ ] 9.6 Write unit tests for client context chatbot
    - Test client search returns correct results
    - Test context building is called correctly
    - Test prompt includes client context
    - Test response streaming works
    - Test metadata extraction accuracy
    - _Requirements: Verify chat integration_

- [x] 10. Create client chat API router
  - [x] 10.1 Create `client_chat_router.py` in `backend/app/modules/knowledge/`
    - Define router with prefix `/api/v1/knowledge/client-chat`
    - Add OpenAPI tags for documentation
    - _Requirements: API endpoint structure_

  - [x] 10.2 Implement `GET /clients/search` endpoint
    - Accept `q` query parameter (min 1 char, max 100)
    - Accept `limit` parameter (default 20, max 50)
    - Require authentication via `get_current_user`
    - Return list of `ClientSearchResult`
    - _Requirements: 1.2 (typeahead search), 1.8 (auth required)_

  - [x] 10.3 Implement `GET /clients/{client_id}/profile` endpoint
    - Validate client belongs to user's tenant
    - Fetch profile using context builder
    - Include connection status and freshness warning
    - Return `ClientProfileResponse`
    - _Requirements: 1.5 (display client info), 10.2 (NEEDS_REAUTH warning)_

  - [x] 10.4 Create request/response schemas in `client_chat_schemas.py`
    - Define `ClientSearchResult` schema
    - Define `ClientProfileResponse` schema
    - Define `ClientChatRequest` schema
    - Define `ClientChatRequestWithConversation` schema
    - Define `ClientChatCitation` schema
    - Define `ClientChatMetadata` schema
    - Define `ClientChatError` schema
    - _Requirements: API schema definitions_

  - [x] 10.5 Implement `POST /chat/stream` endpoint
    - Accept `ClientChatRequest` body
    - Validate client access for user's tenant
    - Stream SSE events with text chunks
    - Send final event with citations and metadata
    - _Requirements: 3.1-3.7 (context-aware chat)_

  - [x] 10.6 Implement `POST /chat/persistent/stream` endpoint
    - Extend stream endpoint with conversation persistence
    - Create/update `ChatConversation` with `client_id` reference
    - Store client context in message metadata
    - Return conversation_id in final event
    - _Requirements: 5.1-5.5 (session persistence)_

  - [x] 10.7 Register router in knowledge module `__init__.py`
    - Add client_chat_router to module exports
    - Ensure router is included in main app
    - _Requirements: API registration_

  - [ ] 10.8 Write integration tests for API endpoints
    - Test client search returns correct results
    - Test client search enforces tenant isolation
    - Test profile endpoint returns valid data
    - Test profile endpoint returns 404 for invalid client
    - Test chat stream returns SSE events
    - Test chat stream includes client metadata
    - Test persistent chat creates conversation
    - _Requirements: API correctness verification_

- [x] 11. Add conversation client context tracking
  - [x] 11.1 Add `client_id` column to `ChatConversation` model
    - Add nullable foreign key to `xero_connections`
    - Add index for client lookup
    - **Note**: References XeroConnection (org), not XeroClient (contact)
    - _Requirements: 5.5 (display client per message)_

  - [x] 11.2 Add `client_context_metadata` to `ChatMessage` model
    - Store query intent, token count, and data freshness
    - Use JSONB for flexibility
    - _Requirements: 5.5 (conversation history with context)_

  - [x] 11.3 Create migration for conversation context columns
    - Add columns with appropriate defaults
    - Ensure backward compatibility with existing conversations
    - _Requirements: Schema migration_

  - [x] 11.4 Update knowledge repository for client context
    - Modify conversation creation to accept client_id
    - Modify message creation to accept context metadata
    - _Requirements: Repository updates_

---

## Phase 5: Frontend Implementation

- [x] 12. Create client selector component
  - [x] 12.1 Create `ClientSelector.tsx` in `frontend/src/components/assistant/`
    - Implement searchable dropdown with typeahead
    - Debounce search input (300ms)
    - Show loading state during search
    - Display client name, ABN, and organization
    - _Requirements: 1.1-1.2 (client selector with search)_

  - [x] 12.2 Implement client search API hook
    - Create search functionality in assistant page
    - Call `/api/v1/knowledge/client-chat/clients/search`
    - Handle loading, error, and empty states
    - _Requirements: 1.2 (typeahead API integration)_

  - [x] 12.3 Create client context header/badge component
    - Display selected client name and GST status
    - Show visual indicator for client context mode
    - Include change client button
    - Style with distinct background color (teal accent)
    - **Note**: Implemented as `ClientContextHeader` in assistant page
    - _Requirements: 1.3-1.4 (visual distinction for context mode)_

  - [ ] 12.4 Write component tests for client selector
    - Test search input triggers API call
    - Test results display correctly
    - Test client selection callback
    - Test clear button behavior
    - _Requirements: Frontend component testing_

- [x] 13. Update assistant page with client context
  - [x] 13.1 Add client context state to `AssistantPage`
    - Create state for `selectedClient: ClientSearchResult | null`
    - Create state for client profile data
    - _Requirements: 5.1-5.3 (client selection state)_

  - [x] 13.2 Integrate client selector modal
    - Position selector triggered by "New Conversation" button
    - Allow choosing between General and Client-Specific conversations
    - _Requirements: 1.1 (selector in chat header)_

  - [x] 13.3 Integrate client context header
    - Show when client is selected
    - Display client profile info from API
    - Handle change action to switch clients
    - _Requirements: 1.3-1.6 (header and change action)_

  - [x] 13.4 Update chat submission to include client context
    - Modify `handleSubmit` to pass `client_id` to API
    - Use client-chat streaming endpoint when client selected
    - _Requirements: 3.1 (send client_id with query)_

  - [x] 13.5 Add conversation filtering by client
    - Filter pills for All, General, and per-client conversations
    - Show conversation count per client
    - _Requirements: 5.4 (filter conversations by client)_

  - [x] 13.6 Add help tooltip for client context questions
    - Show available question categories (Tax, Cash Flow, GST, Compliance)
    - Display example questions for each category
    - **Note**: Implemented as `ClientContextHelpTooltip` component
    - _Requirements: User guidance for feature discovery_

- [x] 14. Add data freshness and error handling UI
  - [x] 14.1 Add freshness indicator in client header
    - Display "Synced Today/Yesterday/X days ago"
    - Show warning when data is stale (> 24 hours)
    - _Requirements: 3.7 (freshness indicator), 9.4 (stale warning)_

  - [x] 14.2 Show connection status in header
    - Display refresh button for data sync
    - _Requirements: 10.2 (connection status)_

  - [x] 14.3 Update message display for client data references
    - Parse metadata from SSE response
    - Display citations panel with sources
    - _Requirements: 3.7 (data freshness in response)_

  - [x] 14.4 Handle error states gracefully
    - Show user-friendly error messages
    - Handle loading states throughout
    - _Requirements: 10.1-10.6 (error handling)_

- [x] 15. Update API client library
  - [x] 15.1 Add client chat API functions in `frontend/src/lib/api/knowledge.ts`
    - Add `searchClients(query, limit)` function
    - Add `getClientProfile(clientId)` function
    - Add `streamClientChat(request)` function
    - _Requirements: API client functions_

  - [x] 15.2 Add TypeScript types for client chat
    - Add `ClientSearchResult` interface
    - Add `ClientProfileResponse` interface
    - Add `ClientChatRequest` interface
    - Add `ClientChatMetadata` interface
    - _Requirements: Type safety_

---

## Phase 6: Testing and Polish

- [ ] 16. Complete integration test suite
  - [ ] 16.1 Write integration tests for aggregation pipeline
    - Test full aggregation flow from sync to computed summaries
    - Test aggregation for client with complete data
    - Test aggregation for client with partial data
    - Test aggregation for client with no data (zeros stored)
    - _Requirements: 4.1-4.8 (aggregation correctness)_

  - [ ] 16.2 Write integration tests for context building
    - Test context build with all tiers
    - Test context build with missing aggregations (fallback)
    - Test token budget enforcement
    - Test intent-based summary selection
    - _Requirements: 2.1-2.8 (context building correctness)_

  - [ ] 16.3 Write integration tests for chat API
    - Test full chat flow with client context
    - Test SSE streaming with proper event types
    - Test conversation persistence with client_id
    - Test error responses for invalid clients
    - _Requirements: 3.1-3.7, 5.1-5.6 (chat flow correctness)_

  - [ ] 16.4 Write security integration tests
    - Test client search respects tenant isolation
    - Test chat endpoint rejects cross-tenant client access
    - Test RLS policies on aggregation tables
    - _Requirements: 8.1-8.6 (security verification)_

- [ ] 17. Write E2E tests
  - [ ] 17.1 Create E2E test for complete user flow
    - Navigate to assistant page
    - Search and select a client
    - Verify client badge appears
    - Submit question and wait for response
    - Verify response includes client-specific data
    - Clear client and verify return to general mode
    - _Requirements: End-to-end flow verification_

  - [ ] 17.2 Create E2E test for error scenarios
    - Test flow when no Xero connections exist
    - Test flow when client has no data
    - Test flow with stale data warning
    - _Requirements: 10.1-10.6 (error UI verification)_

- [ ] 18. Performance testing
  - [ ] 18.1 Add performance metrics to context building
    - Instrument `build_context()` with timing
    - Log p95 latency for context retrieval
    - Target: < 2 seconds for full context build
    - _Requirements: NFR Performance (2s context build)_

  - [ ] 18.2 Add performance metrics to chat endpoint
    - Instrument full chat flow timing
    - Log p95 end-to-end latency
    - Target: < 10 seconds including LLM generation
    - _Requirements: NFR Performance (10s total latency)_

  - [ ] 18.3 Test client search performance at scale
    - Test with 1000+ clients in tenant
    - Verify sub-second search response
    - Add index if needed for performance
    - _Requirements: NFR Scalability (1000+ clients)_

  - [ ] 18.4 Test aggregation sync overhead
    - Measure sync duration with and without aggregation
    - Verify < 30% overhead from aggregation
    - Optimize queries if needed
    - _Requirements: NFR Performance (30% sync overhead)_

- [ ] 19. Final polish and documentation
  - [x] 19.1 Add observability logging
    - Log connection_id, query_intent, context_tokens, latency_ms for each request
    - Exclude sensitive data (amounts, ABN, names) from logs
    - Add error logging with appropriate detail
    - _Requirements: NFR Observability (structured logging), 8.3 (no sensitive data in logs)_

  - [ ] 19.2 Update OpenAPI documentation
    - Ensure all endpoints have proper descriptions
    - Document request/response schemas
    - Add example values for testing
    - _Requirements: API documentation_

  - [ ] 19.3 Code review and cleanup
    - Review all new code for consistency
    - Remove any debug code or TODOs
    - Ensure proper error handling throughout
    - _Requirements: Code quality_

---

## Implementation Summary

### Completed
- **Phase 1**: All aggregation models and migrations ✓
- **Phase 2**: Aggregation repository, service, and Celery task ✓
- **Phase 3**: Intent detector, token budget manager, context builder ✓
- **Phase 4**: Client chatbot, API router, conversation tracking ✓
- **Phase 5**: Frontend client selector, assistant page, API client ✓

### Pending
- **Phase 6**: Unit tests, integration tests, E2E tests, performance tests
- Some unit tests scattered through phases 1-5

### Key Implementation Notes

1. **Data Model Fix**: All aggregations use `connection_id` (XeroConnection/organization) not `client_id` (XeroClient/contact). This is because financial data belongs to the organization, not individual contacts.

2. **Organisation Profile Sync**: Added automatic sync of entity type, GST status from Xero Organisation API during full sync.

3. **Help Tooltip**: Added `ClientContextHelpTooltip` component to educate users about available question types.

4. **Task Registration**: `aggregation` module must be imported in `backend/app/tasks/__init__.py` for Celery to register the task.

---

## Notes

- **Dependencies**: Each phase builds on the previous. Phase 1 must complete before Phase 2, etc.
- **Parallel Work**: Within Phase 3, intent detector (T6) and token budget manager (T7) can be developed in parallel. Within Phase 5, client selector (T12) and API client (T15) can be developed in parallel.
- **Testing Strategy**: Unit tests are integrated into each implementation task. Integration and E2E tests are consolidated in Phase 6.
- **Context Documents**: During implementation, refer to `spec.md` for detailed requirements and `plan.md` for component interfaces and data structures.
