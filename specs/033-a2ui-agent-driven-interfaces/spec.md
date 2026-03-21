# Feature Specification: A2UI Agent-Driven Interfaces

**Feature Branch**: `033-a2ui-agent-driven-interfaces`
**Created**: 2026-01-02
**Status**: Draft
**Input**: Enable AI agents to generate dynamic, context-aware native UIs using Google's A2UI protocol. Transform Clairo from static screens to intelligent interfaces that adapt based on user context, time of day, device type, and what the AI discovers in the data.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Dynamic Insight Presentation (Priority: P1)

As an accountant, when AI discovers important findings about a client, I want to see a dynamically generated interface that shows exactly what I need to know - charts for trends, tables for comparisons, and action buttons relevant to the finding - rather than a generic text summary.

**Why this priority**: This is the core value proposition. AI insights are already generated; A2UI transforms how they're presented. This directly improves the most valuable feature in Clairo.

**Independent Test**: Can be fully tested by having an AI agent generate insight UI for different finding types (cash flow warning, GST variance, missing documents) and verifying the appropriate components render.

**Acceptance Scenarios**:

1. **Given** an AI agent discovers a critical cash flow issue, **When** the insight is displayed, **Then** the UI includes an alert card, line chart showing projection, and action buttons for scheduling client calls
2. **Given** an AI agent discovers a minor variance, **When** the insight is displayed, **Then** the UI shows a simple info card without complex visualizations
3. **Given** an AI agent identifies multiple issues of varying severity, **When** the insight is displayed, **Then** critical issues appear prominently with expanded detail, while minor issues are collapsed

---

### User Story 2 - Context-Aware Dashboard (Priority: P1)

As an accountant, when I open Clairo each morning, I want to see a dashboard personalized to what matters RIGHT NOW - urgent clients at the top, upcoming deadlines visualized, and on-track clients collapsed - instead of the same alphabetical grid every time.

**Why this priority**: The dashboard is the first thing users see. A personalized, context-aware dashboard demonstrates immediate value and differentiates Clairo from competitors.

**Independent Test**: Can be fully tested by accessing the dashboard at different times (Monday morning, Friday afternoon, mid-week) and verifying the layout adapts appropriately.

**Acceptance Scenarios**:

1. **Given** it's Monday 9am and I have 3 urgent clients, **When** I view the dashboard, **Then** urgent clients appear first with action buttons, followed by this week's deadline timeline, with on-track clients collapsed
2. **Given** it's Friday 4pm, **When** I view the dashboard, **Then** I see a week summary (completed work), next week preview, and suggested weekend priorities
3. **Given** I have no urgent items, **When** I view the dashboard, **Then** the layout emphasizes upcoming deadlines and proactive opportunities rather than empty "urgent" sections

---

### User Story 3 - Camera-First Mobile Document Capture (Priority: P1)

As an accountant or business owner on a mobile device needing to upload a document, I want the interface to immediately offer camera capture with smart guides rather than making me navigate through menus to find an upload option.

**Why this priority**: Mobile document capture is a critical user journey. Context-aware UI (camera-first on mobile vs file picker on desktop) dramatically improves completion rates.

**Independent Test**: Can be fully tested by accessing a document request on mobile device and verifying camera is the primary action, with file upload as secondary option.

**Acceptance Scenarios**:

1. **Given** I'm viewing a document request on mobile, **When** the UI loads, **Then** a camera capture component is the primary action with "Capture Document" prominent
2. **Given** I'm viewing the same request on desktop, **When** the UI loads, **Then** a file upload component is primary with drag-and-drop zone
3. **Given** an urgent document request on mobile, **When** the UI loads, **Then** an urgency banner appears above the camera capture with countdown to deadline

---

### User Story 4 - Ad-Hoc Query Visualization (Priority: P2)

As an accountant, when I ask a natural language question like "Which clients have declining revenue but increasing expenses?", I want the AI to generate a visual answer with relevant charts, tables, and filters - not just text or a redirect to a pre-built report.

**Why this priority**: This enables infinite flexibility without building infinite reports. High value but requires robust A2UI foundation from P1 stories.

**Independent Test**: Can be fully tested by asking 5 different analytical questions and verifying each generates appropriate visual components (scatter plots for comparisons, tables for lists, bar charts for rankings).

**Acceptance Scenarios**:

1. **Given** I ask "which clients are at risk?", **When** the AI responds, **Then** I see a data table with risk indicators, sortable columns, and filter options
2. **Given** I ask "show me revenue trends across all clients", **When** the AI responds, **Then** I see a multi-line chart with interactive legend and export button
3. **Given** I ask a question with no matching data, **When** the AI responds, **Then** I see a helpful message explaining why and suggesting alternative queries

---

### User Story 5 - BAS Review Exception Focus (Priority: P2)

As an accountant reviewing a BAS, I want the AI to show me ONLY the items that need attention - anomalies, variances, potential issues - with full details collapsed for normal items, so I can focus review time on what matters.

**Why this priority**: Reduces BAS review time significantly. Requires A2UI infrastructure and confidence in AI anomaly detection.

**Independent Test**: Can be fully tested by reviewing a BAS with known anomalies and verifying only those items are expanded with explanations while normal items are collapsed.

**Acceptance Scenarios**:

1. **Given** a BAS with 2 anomalies out of 20 fields, **When** I view the review screen, **Then** only the 2 anomalies are expanded with explanations, the rest are collapsed under "All fields normal"
2. **Given** an anomaly is identified, **When** I view it, **Then** I see the expected value, actual value, variance percentage, and suggested explanation
3. **Given** I want to see all fields anyway, **When** I click "View All Details", **Then** all fields expand with full BAS data

---

### User Story 6 - End-of-Day Summary (Priority: P3)

As an accountant, at the end of my workday, I want the AI to generate a summary of what I accomplished, what's waiting on clients, and what to prioritize tomorrow - formatted for easy timesheet entry.

**Why this priority**: Nice-to-have productivity feature. Demonstrates A2UI's ability to aggregate and present contextual information.

**Independent Test**: Can be fully tested by clicking "End Day" and verifying a summary generates with completed items, pending items, and time estimates.

**Acceptance Scenarios**:

1. **Given** I click "End Day" after working on 5 clients, **When** the summary generates, **Then** I see completed work with time estimates, pending responses, and tomorrow's suggested priorities
2. **Given** I have items waiting on client response, **When** the summary shows, **Then** overdue items are highlighted with "follow up" suggestions
3. **Given** I click "Export to Timesheet", **When** the export runs, **Then** the data formats appropriately for common timesheet systems

---

### Edge Cases

- What happens when the AI agent fails to generate A2UI? Fallback to text-only response with "Rich view unavailable" message
- What happens when a component type is not in the catalog? Render as generic card with raw data display
- What happens when device type changes mid-session (e.g., desktop to tablet)? Re-render with appropriate component variants on next interaction
- What happens when streaming UI and connection drops? Show partial UI with "Loading..." for incomplete sections, allow retry

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST render A2UI components from JSON payloads using the component catalog
- **FR-002**: System MUST map all A2UI abstract types to shadcn/ui native components
- **FR-003**: System MUST support progressive/streaming rendering as AI generates components
- **FR-004**: System MUST provide data model binding between A2UI dataModelUpdate and component state
- **FR-005**: System MUST handle component interactions (clicks, inputs) and route to appropriate actions
- **FR-006**: AI agents MUST generate A2UI alongside text responses for supported insight types
- **FR-007**: System MUST provide fallback rendering when A2UI generation fails
- **FR-008**: System MUST detect device context (mobile/desktop) and adjust component selection
- **FR-009**: System MUST support at least 30 component types in the catalog (see Appendix)
- **FR-010**: System MUST cache common A2UI patterns to reduce agent computation time
- **FR-011**: System MUST provide accessibility support (ARIA roles, keyboard navigation) for all A2UI components
- **FR-012**: System MUST log A2UI rendering performance for monitoring

### Key Entities

- **A2UI Message**: The JSON payload containing surfaceUpdate, dataModelUpdate, and rendering instructions
- **Component Catalog**: Registry mapping A2UI types to React components
- **Data Model Context**: Reactive state container for component data bindings
- **Rendering Session**: Tracks progressive rendering state for a single A2UI response

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No - A2UI is presentation-only, does not change auth flows
- [ ] **Data Access Events**: No - A2UI renders data already fetched by existing endpoints
- [x] **Data Modification Events**: Yes - A2UI action buttons may trigger data modifications
- [ ] **Integration Events**: No - A2UI does not directly integrate with external systems
- [ ] **Compliance Events**: No - A2UI is presentation layer, does not affect compliance logic

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| a2ui.action.triggered | User clicks A2UI action button | Action type, target, user, timestamp | 7 years | None |
| a2ui.render.failed | A2UI rendering fails | Error type, component, session_id | 90 days | None |

### Compliance Considerations

- **ATO Requirements**: None specific - A2UI is UI rendering, not data processing
- **Data Retention**: Standard 7 years for action audit trail
- **Access Logging**: No special requirements beyond existing audit system

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can view AI-generated insight UIs within 2 seconds of insight completion
- **SC-002**: Component catalog supports at least 30 reusable UI types at launch
- **SC-003**: Mobile document capture shows camera-first UI on 100% of mobile devices
- **SC-004**: Dashboard personalization results in 40% reduction in clicks-to-action for urgent items
- **SC-005**: Ad-hoc query responses generate appropriate visualizations for 90% of supported query types
- **SC-006**: BAS review time reduced by 30% for BAS periods with anomalies (compared to viewing all fields)
- **SC-007**: A2UI rendering adds no more than 200ms latency compared to static UI rendering
- **SC-008**: 80% of users report dashboard layout matches their priorities (survey metric)

---

## Appendix: Component Catalog (Initial)

| A2UI Type | Native Component | Usage |
|-----------|------------------|-------|
| `alertCard` | `Alert` | Warnings, errors, info messages |
| `dataTable` | `DataTable` | Client lists, transactions, comparisons |
| `lineChart` | `LineChart` | Trends, projections, time series |
| `barChart` | `BarChart` | Comparisons, rankings |
| `pieChart` | `PieChart` | Distributions, breakdowns |
| `card` | `Card` | Generic container |
| `expandableSection` | `Accordion` | Collapsible details |
| `filterBar` | `FilterBar` | Data filtering controls |
| `cameraCapture` | `CameraCapture` | Mobile document capture |
| `fileUpload` | `FileUpload` | Desktop file selection |
| `dateRangePicker` | `DateRangePicker` | Period selection |
| `approvalBar` | `ApprovalButtons` | Approve/reject/query actions |
| `urgencyBanner` | `Banner` | Deadline warnings, alerts |
| `progressIndicator` | `Progress` | Completion status |
| `actionButton` | `Button` | Primary and secondary actions |
| `textInput` | `Input` | Text entry fields |
| `selectField` | `Select` | Dropdown selection |
| `checkbox` | `Checkbox` | Boolean options |
| `avatar` | `Avatar` | User/client images |
| `badge` | `Badge` | Status indicators |
| `tooltip` | `Tooltip` | Hover information |
| `dialog` | `Dialog` | Modal interactions |
| `tabs` | `Tabs` | Tabbed content |
| `timeline` | `Timeline` | Event sequences |
| `statCard` | `StatCard` | Key metrics display |
| `comparisonTable` | `ComparisonTable` | Side-by-side analysis |
| `scatterChart` | `ScatterChart` | Multi-dimensional data |
| `queryResult` | `QueryResult` | Search/query result header |
| `exportButton` | `ExportButton` | CSV/PDF export |
| `skeleton` | `Skeleton` | Loading states |

---

## Implementation Approach: LLM-Driven A2UI

### Core Principle

The LLM **decides dynamically** what UI components to show based on its response content - not pre-canned rules. This is true A2UI where the AI controls both WHAT it says and HOW it's presented.

### How It Works

1. **LLM receives A2UI schema** in its system prompt with available components
2. **LLM analyzes its response** and decides what deserves visual emphasis
3. **LLM outputs** text response + optional `\`\`\`a2ui` JSON block specifying components
4. **Parser extracts** the A2UI specification and builds native components
5. **Frontend renders** the components alongside the text

### Example LLM Output

When asked about GST liabilities, the LLM responds:

```
[Compliance] Based on Q2 2025-26 data, KR8 IT has a net GST liability of $10,224.65...

```a2ui
{
  "components": [
    {"type": "stat_card", "label": "GST Collected (1A)", "value": "$15,420"},
    {"type": "stat_card", "label": "GST Paid (1B)", "value": "$5,196"},
    {"type": "stat_card", "label": "Net Payable", "value": "$10,225", "trend": "up"},
    {"type": "alert", "severity": "warning", "title": "Data Gap", "message": "Q1 2026 shows $0"}
  ],
  "layout": "grid"
}
```

### Supported Component Types (LLM Schema)

| Type | Purpose | Example |
|------|---------|---------|
| `stat_card` | Key metrics | GST figures, totals |
| `alert` | Notices/warnings | Compliance issues, data gaps |
| `line_chart` | Trends over time | Monthly revenue, cash flow |
| `bar_chart` | Comparisons | Expense breakdown |
| `data_table` | Lists | Overdue invoices, top clients |
| `action_button` | Suggested actions | Export, navigate |

### Why LLM-Driven (Not Rule-Based)

- **Context-aware**: LLM knows what's important in its specific response
- **Flexible**: Can generate novel combinations for any query type
- **Intelligent**: Decides when visualization adds value vs. when text is enough
- **Adaptive**: Can emphasize different aspects based on user context

---

## Dependencies

- **Phase C (AI Agents)**: COMPLETE - Required for A2UI generation
- **Spec 038 (Observability)**: OPTIONAL - Useful for monitoring A2UI performance
- **Spec 032 (PWA/Mobile)**: COMPLETE - Required for camera capture components
