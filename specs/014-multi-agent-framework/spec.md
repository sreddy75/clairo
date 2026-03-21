# Requirements Document: Multi-Agent Framework

## Introduction

This document defines the requirements for implementing a multi-agent AI system for Clairo that enables specialized agents to collaborate in answering complex accountant questions. The system builds upon the existing Knowledge Base + RAG Engine (Spec 012) and Client-Context Chat (Spec 013) to provide comprehensive, multi-faceted responses that combine compliance knowledge, client-specific data analysis, strategic advisory, and quality assessment.

The multi-agent framework introduces an Orchestrator that routes queries to appropriate specialist agents (Compliance, Quality, Strategy, and Insight), manages inter-agent communication, synthesizes responses from multiple sources, and escalates to human accountants when confidence is low or scenarios are too complex for automated handling.

### Key Goals

- Enable complex questions to be answered by combining expertise from multiple specialist domains
- Maintain response quality with confidence scoring and human escalation
- Keep response times under 15 seconds and costs under $0.50 per query
- Provide full traceability of agent contributions for audit and debugging

---

## Requirements

### Requirement 1: Orchestrator Agent - Query Routing

**User Story:** As an accountant, I want the system to automatically route my complex question to the right specialist agent(s), so that I get comprehensive answers without needing to know which agent handles what.

#### Acceptance Criteria

1. WHEN an accountant submits a query THEN the Orchestrator SHALL analyze the query intent and determine which specialist agent(s) are required to answer it.

2. WHEN a query matches a single domain (e.g., pure GST question) THEN the Orchestrator SHALL route to only the relevant specialist agent to minimize latency and cost.

3. WHEN a query spans multiple domains (e.g., "How can this client reduce their tax?") THEN the Orchestrator SHALL route to all relevant specialist agents in parallel.

4. WHEN the Orchestrator routes a query THEN it SHALL pass the relevant client context (from Spec 013 context builder) to each specialist agent.

5. WHEN the Orchestrator cannot determine appropriate routing THEN it SHALL default to routing to the Compliance Agent with a fallback flag indicating uncertainty.

6. WHEN routing decisions are made THEN the Orchestrator SHALL log the routing decision including: query hash, detected intents, selected agents, and reasoning for audit purposes.

### Requirement 2: Orchestrator Agent - Response Synthesis

**User Story:** As an accountant, I want multi-agent responses combined into a single coherent answer, so that I can easily understand the complete picture without piecing together separate responses.

#### Acceptance Criteria

1. WHEN multiple specialist agents return responses THEN the Orchestrator SHALL synthesize them into a single coherent response that integrates all perspectives.

2. WHEN synthesizing responses THEN the Orchestrator SHALL maintain clear attribution indicating which agent contributed which insight (e.g., "[Compliance] GST registration is required..." "[Insight] Revenue trend shows...").

3. WHEN specialist agents provide conflicting information THEN the Orchestrator SHALL highlight the conflict and present both perspectives with confidence scores.

4. WHEN synthesizing THEN the Orchestrator SHALL prioritize information by relevance to the original query, placing the most directly relevant content first.

5. WHEN a specialist agent fails to respond within timeout THEN the Orchestrator SHALL synthesize available responses and indicate which specialist's input is missing.

6. WHEN all responses are synthesized THEN the Orchestrator SHALL include a combined confidence score derived from individual agent confidence scores.

### Requirement 3: Compliance Agent

**User Story:** As an accountant, I want detailed compliance advice based on current ATO rules and regulations, so that I can ensure my clients meet their tax obligations correctly.

#### Acceptance Criteria

1. WHEN the Compliance Agent receives a query THEN it SHALL query the `compliance_knowledge` namespace in Pinecone for relevant ATO rules, rulings, and guidance.

2. WHEN retrieving compliance information THEN the Compliance Agent SHALL use the existing RAG pipeline from Spec 012 with Voyage-3.5-lite embeddings.

3. WHEN responding to GST questions THEN the Compliance Agent SHALL reference specific ATO rulings, GST Act sections, or official guidance documents with citations.

4. WHEN responding to BAS questions THEN the Compliance Agent SHALL explain calculation rules and reference current thresholds and deadlines.

5. WHEN the Compliance Agent encounters a question about recent rule changes (within last 90 days) THEN it SHALL flag the response as "may require verification" due to potential knowledge staleness.

6. WHEN providing compliance advice THEN the Compliance Agent SHALL include a confidence score (0.0-1.0) based on citation quality and retrieval relevance scores.

7. IF client context is provided THEN the Compliance Agent SHALL tailor advice to the client's entity type, GST registration status, and revenue bracket.

### Requirement 4: Quality Agent

**User Story:** As an accountant, I want the system to identify data quality issues in my client's records, so that I can address problems before they affect BAS lodgement or cause compliance issues.

#### Acceptance Criteria

1. WHEN the Quality Agent receives a query about data issues THEN it SHALL analyze the client's financial data from aggregation tables for common problems.

2. WHEN analyzing data THEN the Quality Agent SHALL check for: duplicate transactions, missing GST codes, unreconciled items, coding inconsistencies, and unusual patterns.

3. WHEN a data quality issue is detected THEN the Quality Agent SHALL categorize it by severity (Critical, Warning, Info) and provide specific remediation steps.

4. WHEN checking GST coding THEN the Quality Agent SHALL identify transactions that may have incorrect tax codes based on account type and description patterns.

5. WHEN analyzing reconciliation THEN the Quality Agent SHALL identify bank transactions that remain unmatched beyond typical periods.

6. WHEN responding THEN the Quality Agent SHALL provide specific transaction references or date ranges for identified issues.

7. WHEN no issues are found THEN the Quality Agent SHALL confirm data quality status and specify what checks were performed.

### Requirement 5: Strategy Agent

**User Story:** As an accountant, I want strategic tax optimization and business advice for my clients, so that I can proactively help them improve their financial position.

#### Acceptance Criteria

1. WHEN the Strategy Agent receives a query THEN it SHALL query the `strategic_advisory` namespace in Pinecone for relevant strategies and advice.

2. WHEN providing tax optimization advice THEN the Strategy Agent SHALL consider the client's entity type, revenue bracket, and industry to provide tailored recommendations.

3. WHEN advising on business structure THEN the Strategy Agent SHALL explain implications for taxation, liability, and compliance obligations.

4. WHEN the Strategy Agent identifies an optimization opportunity THEN it SHALL estimate potential savings or benefits where quantifiable.

5. WHEN providing strategic advice THEN the Strategy Agent SHALL clearly distinguish between general information and advice that requires professional judgment.

6. IF the strategy involves significant complexity or risk THEN the Strategy Agent SHALL flag the response for accountant review before presenting to end users.

7. WHEN responding THEN the Strategy Agent SHALL include relevant disclaimers about the advisory nature of suggestions.

### Requirement 6: Insight Agent

**User Story:** As an accountant, I want the system to automatically detect patterns, anomalies, and important trends in client data, so that I can proactively advise clients on emerging issues or opportunities.

#### Acceptance Criteria

1. WHEN the Insight Agent receives a query THEN it SHALL analyze both knowledge base sources and client-specific financial data.

2. WHEN analyzing client data THEN the Insight Agent SHALL detect significant trends in revenue, expenses, and cash flow over the past 6-12 months.

3. WHEN an anomaly is detected (e.g., unusual expense spike, revenue drop) THEN the Insight Agent SHALL quantify the deviation from normal patterns and suggest potential causes.

4. WHEN GST registration thresholds are relevant THEN the Insight Agent SHALL project whether the client is approaching or exceeding the $75,000 threshold based on revenue trends.

5. WHEN cash flow patterns indicate risk THEN the Insight Agent SHALL identify the specific indicators (e.g., growing AR aging, declining collections) and timeline.

6. WHEN providing insights THEN the Insight Agent SHALL distinguish between observed facts (data-driven) and inferences (pattern-based conclusions).

7. WHEN insights could trigger compliance requirements (e.g., approaching GST threshold) THEN the Insight Agent SHALL explicitly flag these as "Compliance Alert" items.

### Requirement 7: Agent Communication Protocol

**User Story:** As a system operator, I want agents to communicate through a standardized protocol, so that the system is maintainable, debuggable, and extensible.

#### Acceptance Criteria

1. WHEN agents communicate THEN they SHALL use a standardized message format including: message_id, source_agent, target_agent, message_type, payload, timestamp, and correlation_id.

2. WHEN an agent requests information from another agent THEN the requesting agent SHALL specify the exact data needed and expected response format.

3. WHEN an agent responds to a request THEN it SHALL include: the original request_id, response data, confidence score, processing time, and token usage.

4. WHEN agents share findings THEN they SHALL use a structured format that includes: finding_type, evidence, confidence, and relevance_to_query.

5. WHEN an agent encounters an error THEN it SHALL return a standardized error response including error_type, error_message, and whether the error is recoverable.

6. WHEN the Orchestrator initiates a multi-agent query THEN it SHALL generate a unique correlation_id that all agents include in their messages for distributed tracing.

### Requirement 8: Human Escalation

**User Story:** As an accountant, I want the system to recognize when it needs my input rather than providing potentially incorrect automated answers, so that I can step in for complex scenarios.

#### Acceptance Criteria

1. WHEN an agent's confidence score falls below 0.6 THEN the system SHALL flag the response as requiring human review.

2. WHEN confidence falls below 0.4 THEN the system SHALL escalate to the accountant before presenting any automated response.

3. WHEN the query involves: complex multi-entity structures, international taxation, significant financial decisions (>$100k impact), or potential penalties THEN the system SHALL automatically escalate to human review.

4. WHEN escalating THEN the system SHALL provide the accountant with: the original query, partial analysis from agents, specific areas of uncertainty, and suggested follow-up questions.

5. WHEN escalation occurs THEN the system SHALL log the escalation reason and allow the accountant to provide a response that is recorded for future learning.

6. WHEN an accountant overrides or corrects an agent response THEN the system SHALL log the correction with the accountant's reasoning for quality improvement analysis.

7. IF the accountant is unavailable for escalation THEN the system SHALL queue the query and provide the user with an estimated response time.

### Requirement 9: Token Budget Management

**User Story:** As a system operator, I want the multi-agent system to operate within defined token budgets, so that costs remain predictable and sustainable.

#### Acceptance Criteria

1. WHEN a multi-agent query is initiated THEN the Orchestrator SHALL allocate a total token budget (default: 15,000 tokens) distributed across agents.

2. WHEN routing to multiple agents THEN the Orchestrator SHALL divide the budget based on query complexity and expected agent token needs.

3. WHEN an agent approaches its token budget THEN it SHALL summarize remaining context rather than truncating mid-response.

4. WHEN budget is exhausted before all agents complete THEN the Orchestrator SHALL synthesize available responses and indicate which agents were token-limited.

5. WHEN the total cost of a query exceeds $0.50 THEN the system SHALL log a warning for cost monitoring but SHALL NOT fail the query.

6. WHEN token usage is tracked THEN the system SHALL record per-agent token consumption for cost attribution and optimization.

### Requirement 10: Performance and Latency

**User Story:** As an accountant, I want multi-agent queries to complete within 15 seconds, so that the system remains responsive for client conversations.

#### Acceptance Criteria

1. WHEN a multi-agent query is initiated THEN the Orchestrator SHALL execute independent agent calls in parallel to minimize total latency.

2. WHEN a specialist agent does not respond within 10 seconds THEN the Orchestrator SHALL timeout that agent and proceed with available responses.

3. WHEN latency exceeds 12 seconds THEN the Orchestrator SHALL provide a preliminary response with available data and continue processing in background if possible.

4. WHEN all agents complete successfully THEN the total response time (query receipt to response delivery) SHALL be under 15 seconds for 95th percentile queries.

5. WHEN streaming is enabled THEN the Orchestrator SHALL begin streaming the response as soon as the first agent completes, appending additional agent insights as they arrive.

6. WHEN latency targets are missed THEN the system SHALL log detailed timing breakdown per agent for performance analysis.

### Requirement 11: Fallback Behavior

**User Story:** As a system operator, I want the system to gracefully handle agent failures, so that users always receive some useful response even when components fail.

#### Acceptance Criteria

1. IF a specialist agent fails to respond THEN the Orchestrator SHALL continue with available agents and indicate the missing perspective in the response.

2. IF the primary LLM service (Claude) is unavailable THEN the system SHALL return a cached response if available for similar queries, or a helpful error message.

3. IF the knowledge base (Pinecone) is unavailable THEN agents SHALL fall back to client context data only and clearly state that compliance knowledge was unavailable.

4. IF client context cannot be retrieved THEN agents SHALL respond with general information only and explicitly note the lack of client-specific analysis.

5. WHEN fallback behavior is triggered THEN the system SHALL log the failure reason and which fallback path was taken.

6. WHEN all critical services fail THEN the system SHALL return a standardized error response directing the user to retry or contact support.

### Requirement 12: Audit and Traceability

**User Story:** As an accountant, I want to see which agent contributed each part of a response, so that I can verify the reasoning and sources used.

#### Acceptance Criteria

1. WHEN a response is generated THEN the system SHALL store an audit record including: query, all agent responses (pre-synthesis), final synthesized response, and timing data.

2. WHEN presenting a response THEN the system SHALL provide optional "detailed view" showing individual agent contributions with their confidence scores.

3. WHEN citations are included in responses THEN each citation SHALL be traceable to the specific knowledge chunk and Pinecone namespace used.

4. WHEN decisions are made (routing, escalation, synthesis) THEN the system SHALL log the decision reasoning in a structured, queryable format.

5. WHEN an audit record is created THEN it SHALL be retained for a minimum of 7 years per ATO record-keeping requirements.

6. WHEN audit data is accessed THEN the system SHALL require appropriate authorization and log the access for compliance purposes.

---

## Non-Functional Requirements

### Performance

1. **Response Time:** Multi-agent queries SHALL complete within 15 seconds for 95th percentile.
2. **Throughput:** The system SHALL support at least 10 concurrent multi-agent queries per accountant practice.
3. **Availability:** The multi-agent system SHALL maintain 99.9% availability during business hours (AEST).

### Cost

1. **Per-Query Cost:** Average cost per complex multi-agent query SHALL be under $0.50.
2. **Token Efficiency:** Token usage SHALL be optimized through context reuse and smart truncation.
3. **Cost Visibility:** Per-query cost breakdown SHALL be available for billing and optimization.

### Security

1. **Data Isolation:** Client data SHALL only be accessible to authorized agents processing that client's query.
2. **Audit Logging:** All agent actions and decisions SHALL be logged with tamper-evident storage.
3. **Access Control:** Agent escalations and overrides SHALL respect the user's role permissions.

### Scalability

1. **Horizontal Scaling:** Agent workloads SHALL support horizontal scaling through task queues.
2. **Knowledge Base Growth:** The agent system SHALL handle knowledge base growth without performance degradation.

### Maintainability

1. **Agent Modularity:** Each specialist agent SHALL be independently deployable and configurable.
2. **Prompt Versioning:** Agent prompts SHALL be versioned and auditable.
3. **Monitoring:** Agent health, latency, and error rates SHALL be exposed via metrics endpoints.

---

## Out of Scope

The following items are explicitly out of scope for this specification:

1. **Business Owner Interface:** Direct business owner interaction with agents (Phase D)
2. **Agent Learning:** Automated learning from accountant corrections (future enhancement)
3. **Custom Agent Creation:** Ability for accountants to create custom specialist agents
4. **Multi-Practice Agents:** Agents that span multiple accountant practices
5. **Real-time ATO Integration:** Direct ATO API calls for live compliance data

---

## Dependencies

- **Spec 012:** Knowledge Base + RAG Engine (Pinecone, Voyage embeddings, Claude API)
- **Spec 013:** Client-Context Chat (Context builder, intent detection, aggregation service)
- **Infrastructure:** Redis for caching and task queues, PostgreSQL for audit storage

---

## Glossary

| Term | Definition |
|------|------------|
| Orchestrator | Central agent that routes queries and synthesizes responses |
| Specialist Agent | Domain-specific agent (Compliance, Quality, Strategy, Insight) |
| RAG | Retrieval-Augmented Generation |
| Confidence Score | 0.0-1.0 measure of agent certainty in its response |
| Escalation | Routing to human accountant when automated handling is insufficient |
| Correlation ID | Unique identifier linking all messages in a multi-agent query |
