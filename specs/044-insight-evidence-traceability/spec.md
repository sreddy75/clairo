# Feature Specification: Platform-Wide Evidence & Traceability

**Feature Branch**: `044-insight-evidence-traceability`
**Created**: 2026-02-24
**Status**: Draft
**Input**: User description: "Add Evidence & Traceability across the platform — accountants need to verify and validate the data behind all AI-generated recommendations, computed scores, projections, and financial displays"

## Context

A platform-wide audit identified **28 locations** where AI-generated content, computed scores, projections, or derived financial figures are shown to users without adequate evidence, source citations, or methodology transparency. These gaps fall into 5 systemic root causes:

1. **`InsightResponse` schema excludes `data_snapshot`** — all analyzer evidence stored in DB but never reaches frontend
2. **AI context not persisted after LLM calls** — financial data sent to Claude is discarded, no audit trail
3. **No prompt instructions for structured citations** — LLM told to "be specific" but never required to cite sources
4. **Hardcoded thresholds with no user-facing explanation** — users see severity labels/colors without knowing the rules
5. **Confidence scores are arbitrary constants** — users see "85% confidence" that is meaningless

For a tax compliance platform serving accounting professionals, this is a fundamental trust issue. Accountants bear professional liability for advice they give clients — they cannot rely on AI outputs they cannot verify.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Evidence Behind Insight Analysis Options (Priority: P1)

An accountant expands an insight's analysis and sees 2-4 strategic OPTIONS. Each option now includes an **Evidence** section listing the specific data points, figures, and their sources that the AI used to arrive at that recommendation. The accountant can read each evidence item to verify the numbers match their understanding of the client's financials before presenting the options to their client.

**Why this priority**: The OPTIONS/Magic Zone feature is the highest-value AI output in the platform and the most likely to be shared with clients. Without visible evidence, accountants cannot responsibly use these recommendations.

**Independent Test**: Can be fully tested by expanding any insight and verifying that each option card displays labelled evidence items with data source references (e.g., "P&L Q3 2025: Revenue $185,000"). Delivers immediate trust and transparency value.

**Acceptance Scenarios**:

1. **Given** an insight with `generation_type` of `rule_based` or `ai_single`, **When** the accountant clicks "Expand Analysis", **Then** each returned option includes an "Evidence" section listing at least one data point with its source label and value.
2. **Given** an expanded insight displaying OPTIONS, **When** the accountant reads the Evidence section of any option, **Then** every cited figure references a verifiable data source (e.g., "AR Aging", "P&L", "Balance Sheet", "GST Summary", "Monthly Trends").
3. **Given** an option with evidence items, **When** the accountant views the evidence, **Then** each item shows: the data source name, the reporting period or date, and the specific value cited.
4. **Given** a proactively generated Magic Zone insight, **When** the accountant views the OPTIONS, **Then** the same evidence format is present as for manually expanded insights.

---

### User Story 2 - Collapsible Evidence Display (Priority: P1)

The evidence section for each option is presented in a collapsible/expandable format so that accountants who trust the AI can scan options quickly, while those who want to verify can expand the evidence for any specific option without cluttering the view.

**Why this priority**: Evidence must not break the existing user experience. Collapsibility is essential to make evidence a non-intrusive enhancement rather than a UI burden.

**Independent Test**: Can be tested by verifying that evidence sections are collapsed by default, expand on click, and collapse again on second click, without affecting the options card layout.

**Acceptance Scenarios**:

1. **Given** an expanded insight with OPTIONS and evidence, **When** the accountant views the detail panel, **Then** each option's evidence section is collapsed by default showing only a summary indicator (e.g., "3 data points").
2. **Given** a collapsed evidence section, **When** the accountant clicks the evidence toggle, **Then** the section expands to show all cited data points with source labels and values.
3. **Given** an expanded evidence section, **When** the accountant clicks the evidence toggle again, **Then** the section collapses back to the summary indicator.

---

### User Story 3 - Data Snapshot Preservation for Audit Trail (Priority: P1)

When any AI-generated content is produced (insight expansion, AI analyzer insights, Magic Zone insights, multi-client queries), the financial context data that was sent to the AI is captured and stored. This creates an audit trail showing what data the AI had access to at the time of analysis, even if the underlying financial data changes later.

**Why this priority**: Professional accountability requires knowing what informed the AI's analysis. Without this, accountants have no defence if AI-generated advice is later questioned — the input data is gone.

**Independent Test**: Can be tested by expanding an insight, then querying the stored data snapshot via the API to confirm it contains the financial context (profile, summaries, trends) that was used during expansion.

**Acceptance Scenarios**:

1. **Given** an insight being expanded via the orchestrator, **When** the expansion completes, **Then** the financial context sent to the AI is stored in the insight's data snapshot as structured data.
2. **Given** an AI Analyzer generating insights during scheduled generation, **When** insights are created, **Then** each insight's data snapshot contains the financial context that was sent to Claude (not just `{"ai_analysis": True}`).
3. **Given** a previously expanded insight, **When** the accountant retrieves the insight via the API, **Then** the response includes the data snapshot showing what data was available at analysis time.
4. **Given** financial data that has changed since the insight was generated, **When** the accountant views the stored data snapshot, **Then** it reflects the data as it was at generation time, not the current values.

---

### User Story 4 - Agent Chat Citation Consistency (Priority: P2)

When the accountant uses the AI assistant chat with a client selected, the multi-perspective agent response includes inline citations that link financial claims to their data sources and knowledge base claims to their document sources. Citations are interactive — hoverable or clickable to see the source detail.

**Why this priority**: The AI assistant chat is the primary daily interaction surface. Currently, the Knowledge Chatbot has citation instructions but the Agent Orchestrator (the main chat system) has none. This inconsistency undermines trust.

**Independent Test**: Can be tested by asking the AI assistant a client-specific financial question and verifying that the response contains numbered inline citations linked to the CitationsPanel with working source references.

**Acceptance Scenarios**:

1. **Given** an accountant asking a client-specific question in the AI assistant, **When** the agent orchestrator generates a response, **Then** financial claims include inline citation markers referencing specific data sources (e.g., "[AR Aging, Feb 2026]").
2. **Given** an agent response with knowledge base references, **When** the response is rendered, **Then** inline citation markers link to the CitationsPanel entries with source titles and URLs (not empty URLs).
3. **Given** the three chat systems (Knowledge Chatbot, Client Chatbot, Agent Orchestrator), **When** any of them generates a response, **Then** the citation format and quality is consistent across all three.

---

### User Story 5 - Data Freshness Indicators on AI Responses (Priority: P2)

Every AI-generated response or insight that references financial data displays a clear "Data as of [date]" indicator, so accountants know how current the underlying data is. When data is stale (not synced recently), a prominent warning is shown alongside the AI content, not just in the page header.

**Why this priority**: Stale data warnings exist in the client selector header but not alongside the AI responses that use that stale data. An accountant could read an AI analysis referencing week-old data and not notice the staleness.

**Independent Test**: Can be tested by selecting a client with stale data, asking the AI assistant a question, and verifying that the response includes a visible data freshness indicator.

**Acceptance Scenarios**:

1. **Given** an AI response referencing client financial data, **When** the response is rendered, **Then** it includes a "Data as of [last sync date]" indicator.
2. **Given** a client whose data has not been synced for more than 7 days, **When** an AI response or insight is displayed, **Then** a prominent "Stale data" warning appears alongside the content (not just in the header).
3. **Given** an expanded insight, **When** the accountant views the detail panel, **Then** the data freshness timestamp from the stored snapshot is displayed.

---

### User Story 6 - Threshold Transparency for Scores and Alerts (Priority: P2)

When the platform displays computed scores (quality score, BAS variance severity, AR risk classification, balance sheet health indicators), the thresholds and methodology behind those classifications are accessible to the accountant — either via a tooltip, help icon, or expandable explanation.

**Why this priority**: Accountants see colour-coded badges (green/yellow/red) and severity labels (critical/warning) that drive their workflow prioritisation. Without knowing the thresholds, they cannot assess whether the platform's classification aligns with their professional judgement.

**Independent Test**: Can be tested by hovering or clicking a quality score badge, variance severity label, or balance sheet health indicator and verifying that the threshold rules are displayed.

**Acceptance Scenarios**:

1. **Given** a quality score displayed on a client card, **When** the accountant hovers or clicks the score, **Then** a tooltip or popover shows the dimension breakdown with weights (e.g., "Freshness 20%, Reconciliation 30%...").
2. **Given** a BAS variance flagged as "Critical", **When** the accountant hovers or clicks the severity badge, **Then** a tooltip shows the threshold rule (e.g., ">50% change or >$10,000 absolute change").
3. **Given** a balance sheet current ratio shown with a red indicator, **When** the accountant hovers or clicks the indicator, **Then** a tooltip shows the threshold (e.g., "Below 1.0 — industry benchmark is 1.5-2.0").
4. **Given** an AR aging report showing "High Risk", **When** the accountant hovers or clicks the risk badge, **Then** a tooltip shows ">30% overdue = High Risk, >15% = Medium Risk".

---

### User Story 7 - Meaningful Confidence Scores (Priority: P3)

Confidence scores shown alongside AI-generated content reflect the actual quality of the analysis rather than hardcoded constants. The score breakdown is accessible so accountants understand what drives the confidence level.

**Why this priority**: Current confidence scores are meaningless (hardcoded 0.75 for AI insights, 0.85 for Magic Zone). Displaying arbitrary confidence is worse than displaying none — it creates false trust or false doubt.

**Independent Test**: Can be tested by generating insights with varying data quality (full data vs minimal data) and verifying that confidence scores differ meaningfully. The confidence breakdown should be viewable.

**Acceptance Scenarios**:

1. **Given** an AI-generated insight for a client with comprehensive data, **When** the insight is displayed, **Then** the confidence score reflects the data completeness (higher than for a client with sparse data).
2. **Given** an insight or AI response showing a confidence score, **When** the accountant hovers or clicks the confidence indicator, **Then** a breakdown shows the contributing factors (e.g., "Data completeness: High, Knowledge base match: Good, Data freshness: 2 days old").
3. **Given** a multi-client query, **When** the response is returned, **Then** the confidence score is derived from the actual query context, not hardcoded.

---

### User Story 8 - Safe AI Content Export (Priority: P3)

When an accountant copies, emails, or converts AI-generated content to a task, the exported content includes appropriate caveats: data freshness timestamp, confidence level, a disclaimer that the content is AI-generated and should be verified, and any escalation warnings.

**Why this priority**: AI content currently exports as raw text with only "Generated by Clairo". An accountant could email a client AI-generated tax advice with specific dollar amounts and no indication it needs verification.

**Independent Test**: Can be tested by clicking "Email" on an AI chat response and verifying the email body includes a disclaimer, data freshness, and confidence level.

**Acceptance Scenarios**:

1. **Given** an AI response in the chat assistant, **When** the accountant clicks "Email", **Then** the email body includes: a "AI-generated analysis — verify before relying on" disclaimer, the data freshness timestamp, and the confidence score.
2. **Given** an AI response in the chat assistant, **When** the accountant clicks "Copy", **Then** the clipboard content includes the same caveats appended.
3. **Given** an escalated response (confidence below threshold), **When** the accountant exports the content, **Then** the export prominently includes "Professional review recommended" alongside the escalation reason.

---

### Edge Cases

- What happens when the AI fails to include evidence citations in its response? The system should fall back to displaying options without evidence and show "Evidence not available for this analysis".
- What happens when the financial context is empty or minimal (e.g., newly connected client with very little data)? The evidence section should show what limited data was available and the AI should note data limitations in its analysis.
- What happens when an insight is expanded but the client's Xero connection has been disconnected? The expansion should still work using whatever cached/aggregated data is available, and evidence should note the data freshness.
- How does the system handle very large data snapshots? The stored snapshot should be bounded to essential summary data (no raw transactions) to prevent storage growth.
- What happens when the Quality Score uses a proxy metric (e.g., "reconciliation" is actually authorisation status)? The methodology tooltip should clearly state the proxy nature and its limitations.
- What happens when A2UI visualisations fall back to mock data? A clear "Sample Data" watermark must be shown — fabricated financial figures must never appear as real.

## Requirements *(mandatory)*

### Functional Requirements

#### Evidence in Insight OPTIONS (P1)

- **FR-001**: The AI prompt for OPTIONS format MUST instruct the model to include an `**Evidence:**` section per option, listing specific data points with source labels, reporting periods, and values.
- **FR-002**: Each evidence item MUST include: a data source name (e.g., "Profit & Loss", "AR Aging Summary", "GST Summary"), the reporting period or as-of date, and the specific value or metric cited.
- **FR-003**: Evidence MUST follow a hybrid approach: (a) the AI prompt instructs the model to include inline evidence references for human readability, AND (b) the backend independently extracts structured evidence data from the known financial context sent to the AI (not from the AI's text output) and stores it as a structured array. The frontend MUST render evidence from the structured data, not by parsing AI markdown.
- **FR-004**: The frontend MUST render evidence items within each option card as a collapsible section, collapsed by default, sourced from the structured evidence array.
- **FR-005**: When structured evidence data is unavailable (e.g., legacy insights expanded before this feature), the system MUST gracefully degrade — displaying options without evidence and showing a "No evidence data available" indicator. The system MUST NOT rely on regex-parsing the AI's markdown for evidence rendering.
- **FR-006**: The Magic Zone analyzer MUST include evidence citation instructions in its prompts, consistent with the expand endpoint.

#### Data Snapshot Preservation (P1)

- **FR-007**: The system MUST preserve the financial context sent to the AI during insight expansion by storing it in the insight's data snapshot as structured data.
- **FR-008**: The data snapshot MUST capture: client profile summary, financial summaries (P&L, Balance Sheet key figures), AR/AP aging summaries, GST summaries, monthly trend data, and quality scores.
- **FR-009**: The AI Analyzer MUST store the financial context it sends to Claude in `data_snapshot`, replacing the current `{"ai_analysis": True}` stub.
- **FR-010**: The insight API response MUST include the `data_snapshot` field so the frontend can access the underlying data.
- **FR-011**: The stored data snapshot MUST be bounded to summary-level data (no raw transaction lists) with a maximum size of 50KB per snapshot. If the assembled context exceeds 50KB, lower-priority data sections (extended data such as fixed assets, purchase orders, journals) MUST be trimmed first, preserving core summaries (profile, P&L, balance sheet, AR/AP aging, GST, monthly trends, quality scores).

#### Agent Chat Citations (P2)

- **FR-012**: The Agent Orchestrator system prompt MUST instruct the model to use inline citation markers (e.g., `[Source: ATO GST Guide]`, `[Data: AR Aging, Feb 2026]`) to attribute claims to specific knowledge base documents or financial data sources.
- **FR-013**: Citation markers in AI responses MUST be interactive on the frontend — hoverable or clickable to show source detail (title, URL if available, relevance score).
- **FR-014**: Knowledge base citations MUST include the source URL from the vector store metadata (currently available but not propagated).
- **FR-015**: All three chat systems (Knowledge Chatbot, Client Context Chatbot, Agent Orchestrator) MUST use a consistent citation format and quality standard.

#### Data Freshness Indicators (P2)

- **FR-016**: Every AI-generated response or insight that references client financial data MUST display a "Data as of [date]" indicator showing when the underlying data was last synced.
- **FR-017**: When client data is stale (not synced within 7 days), a prominent warning MUST appear alongside the AI content, not only in the page header. The 7-day threshold is a fixed platform-wide value, non-configurable.
- **FR-018**: Expanded insights MUST display the data freshness timestamp from their stored snapshot.

#### Threshold Transparency (P2)

- **FR-019**: Quality score displays MUST provide accessible methodology information showing dimension weights and scoring approach (via tooltip, help icon, or expandable section).
- **FR-020**: BAS variance severity labels (critical/warning/info) MUST include accessible threshold explanations.
- **FR-021**: Balance sheet health indicators (current ratio, debt-to-equity) MUST include accessible threshold explanations with industry benchmark references.
- **FR-022**: AR/AP risk classification labels MUST include accessible threshold explanations.
- **FR-023**: Insight generation thresholds (GST $65K early warning, AR 30%/50% overdue, cash flow 3-month negative trend) MUST be documented in insight detail text when those thresholds trigger an insight.

#### Confidence Score Reform (P3)

- **FR-024**: AI-generated insights MUST have confidence scores derived from actual factors (data completeness, data freshness, knowledge base match quality) rather than hardcoded constants.
- **FR-025**: Confidence indicators MUST provide an accessible breakdown showing contributing factors.
- **FR-026**: The confidence calculation methodology MUST be consistent across all AI-generating components (AI Analyzer, Magic Zone, multi-client query, agent orchestrator).
- **FR-026a**: Until P3 is delivered, hardcoded confidence scores MUST be hidden from the insights UI (not displayed to users). Confidence display MUST only be re-enabled once scores are derived from actual factors. Backend storage of confidence values may continue unchanged.

#### Safe AI Content Export (P3)

- **FR-027**: Email exports of AI content MUST include: an "AI-generated — verify before relying on" disclaimer, data freshness timestamp, and confidence score.
- **FR-028**: Copy-to-clipboard of AI content MUST include the same caveats appended as a footer.
- **FR-029**: Escalated responses MUST include "Professional review recommended" in all export formats.

#### Mock Data Safety (P3)

- **FR-030**: Any UI component that falls back to mock/sample data MUST display a clear "Sample Data" watermark. Fabricated financial figures MUST never appear as real client data.

### Key Entities

- **Evidence Item**: A single structured data point extracted by the backend from the known financial context — includes source name (e.g., "P&L"), period (e.g., "Q3 FY2025"), metric label (e.g., "Revenue"), and value (e.g., "$185,000"). Stored as a structured array in the data snapshot, not parsed from AI text.
- **Data Snapshot**: A structured capture of the financial context available at the time of AI analysis — includes client profile, financial summaries, aging data, GST figures, trend data, and data freshness timestamp. Stored as part of the Insight entity.
- **Threshold Rule**: A defined condition that triggers a classification or alert — includes the metric name, operator, threshold value, and resulting label (e.g., "AR overdue percent > 30% = High Risk").
- **Confidence Breakdown**: A structured object showing the factors contributing to a confidence score — includes data completeness, data freshness, knowledge base match quality, and perspective coverage.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No — this feature does not change authentication or authorization.
- [x] **Data Access Events**: Yes — the system reads financial data (P&L, Balance Sheet, AR/AP, GST figures) to build context for AI analysis.
- [x] **Data Modification Events**: Yes — the insight's data snapshot and detail fields are updated during expansion. Citation data is stored.
- [ ] **Integration Events**: No — this feature does not directly sync with external systems (it uses already-synced aggregated data).
- [ ] **Compliance Events**: No — this feature does not affect BAS lodgements or compliance status directly, but it supports compliance transparency.

### Audit Implementation Requirements

| Event Type              | Trigger                                  | Data Captured                                                       | Retention | Sensitive Data                               |
|-------------------------|------------------------------------------|---------------------------------------------------------------------|-----------|----------------------------------------------|
| insight.expanded        | Insight expansion (manual or Magic Zone) | insight_id, tenant_id, client_id, perspectives_used, evidence_count | 7 years   | None — financial summaries only, no TFN/bank |
| insight.snapshot_stored | Data snapshot saved to insight           | insight_id, snapshot_size_bytes, data_sources_included               | 7 years   | None — aggregate figures only                |
| ai.response_generated   | Any AI response with financial content   | correlation_id, tenant_id, client_id, data_freshness_timestamp      | 7 years   | None — metadata only                         |

### Compliance Considerations

- **ATO Requirements**: The data snapshot creates a point-in-time record of what data informed AI-generated advice, supporting professional accountability if advice is later questioned.
- **Data Retention**: Data snapshots follow the standard 7-year retention period aligned with ATO record-keeping requirements.
- **Access Logging**: Data snapshots are accessible only to authenticated accountants within the same tenant, following existing multi-tenancy access controls.
- **Professional Liability**: Evidence traceability supports accountants' professional indemnity by documenting the basis for AI-assisted advice.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of expanded insights (both manual and Magic Zone) include at least one evidence citation per option within 30 days of deployment.
- **SC-002**: Accountants can identify the data source behind any cited figure in an option within 5 seconds of viewing the evidence section.
- **SC-003**: Data snapshots are stored for all AI-generated insights (expanded, AI Analyzer, Magic Zone), creating a complete audit trail of AI analysis inputs.
- **SC-004**: Evidence display adds no more than 1 second to insight detail panel render time.
- **SC-005**: Accountant trust in AI recommendations improves — measured by a reduction in insight dismissal rate of at least 15% within 60 days of deployment.
- **SC-006**: 100% of AI chat responses include a data freshness indicator when referencing client financial data.
- **SC-007**: All computed scores and classifications (quality, variance severity, risk level, health indicators) include accessible methodology/threshold information.
- **SC-008**: Confidence scores for AI-generated content vary meaningfully based on data quality — clients with comprehensive data produce higher confidence than clients with sparse data.
- **SC-009**: 100% of AI content exports (email, copy) include appropriate disclaimers and metadata.
- **SC-010**: Zero instances of mock/sample data displayed without a watermark in production.

## Clarifications

### Session 2026-02-24

- Q: Should evidence citations be parsed from AI markdown (fragile regex), returned as structured data from backend (reliable), or hybrid? → A: Hybrid — AI includes evidence inline for readability, backend independently extracts structured evidence from known financial context, frontend renders from structured data (not AI text).
- Q: What should happen with meaningless hardcoded confidence scores during interim P1/P2 delivery before P3 reforms them? → A: Hide until reformed — remove confidence display from insights UI in P1; re-enable in P3 when scores are derived from actual factors.
- Q: What is the acceptable maximum data snapshot size per insight? → A: 50KB cap per snapshot. Trim extended data (fixed assets, POs, journals) first if exceeded; always preserve core summaries (profile, P&L, balance sheet, AR/AP, GST, trends, quality).
- Q: Should the 30 FRs be delivered as phased releases or a single release? → A: Phased by priority — P1 ships independently (evidence + snapshots), P2 follows (chat citations, freshness, thresholds), P3 last (confidence reform, export safety, mock data). Each phase independently deployable.
- Q: Should the data staleness threshold (7 days) be fixed or configurable per client/tenant? → A: Fixed 7 days, platform-wide, non-configurable. Aligned with weekly review cycles. Can be parameterised later if needed.

## Rollout Strategy

This feature is delivered in **three independent phases**, each deployable on its own:

- **Phase 1 (P1)**: Evidence in Insight OPTIONS + Collapsible Display + Data Snapshot Preservation + Hide Confidence Scores (FR-001 to FR-011, FR-026a). Delivers core trust and audit trail value.
- **Phase 2 (P2)**: Agent Chat Citation Consistency + Data Freshness Indicators + Threshold Transparency (FR-012 to FR-023). Extends transparency across the platform.
- **Phase 3 (P3)**: Confidence Score Reform + Safe AI Content Export + Mock Data Safety (FR-024 to FR-030). Completes the transparency layer with quality-of-life improvements.

Each phase should be planned and tasked independently. Feedback from earlier phases informs later ones.

## Assumptions

- The existing financial aggregation tables (P&L, Balance Sheet, AR/AP aging, GST summaries, monthly trends) contain sufficient structured data to serve as evidence sources. No new data collection is required.
- The AI model (Claude) can reliably follow structured output instructions for evidence citations when given clear formatting rules in the prompt.
- Summary-level financial data (not raw transactions) is sufficient for evidence traceability. Accountants do not need to drill down to individual transaction level from within the evidence section.
- The existing `data_snapshot` JSONB column on the Insight model can accommodate the expanded snapshot data without schema migration (column already exists, just needs to be populated and exposed).
- Tooltip/popover patterns from shadcn/ui are sufficient for threshold transparency — no new UI component library is needed.
- The quality score "reconciliation" dimension is known to be a proxy for authorisation status. The methodology tooltip should state this transparently rather than requiring the calculation to change.
