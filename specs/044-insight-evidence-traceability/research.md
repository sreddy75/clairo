# Research: Platform-Wide Evidence & Traceability

**Feature**: 044-insight-evidence-traceability
**Date**: 2026-02-24
**Status**: Complete

---

## Research Task 1: Evidence Extraction Patterns

### Decision: Hybrid evidence — backend-extracted structured data + AI inline citations

### Rationale
The backend has full access to structured financial context *before* it is flattened into a text prompt for Claude. By capturing this structured data at the interception point (before prompt construction), the backend can independently build an evidence array without parsing AI text output. The AI is additionally instructed to include inline evidence for human readability, but the frontend renders from the structured backend data — never from parsed AI markdown.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| AI-only structured output (JSON evidence blocks) | Fragile — depends on LLM output formatting compliance; parsing failures degrade silently |
| Regex parsing of AI markdown | Extremely fragile — OPTIONS format already complex; adding evidence regex compounds maintenance burden |
| Backend-only (no AI inline evidence) | AI text reads worse without inline data citations; accountants scanning quickly lose context |

### Key Findings

**Data flow interception points** (where structured context is available before flattening):

1. **Orchestrator `process_query()`** (`orchestrator.py:250-272`):
   - `client_context = await self.context_builder.build_context(connection_id, query)` → `ClientContext` dataclass with `.profile`, `.summaries`, `.raw_data`, `.data_freshness`
   - `multi_context = await self.context_builder.build_perspective_context(...)` → dict with `perspectives.strategy` containing `monthly_trends`, `expense_summaries`, `report_context` (P&L, Balance Sheet, Aged Receivables/Payables), `extended_data`

2. **AI Analyzer `_build_client_context()`** (`ai_analyzer.py:~563`):
   - Builds comprehensive dict with `transactions`, `invoices`, `ar_aging`, `ap_aging`, `expenses`, `gst_data`, `trends`, `quality_scores`, `payroll`
   - Currently stores only `{"ai_analysis": True, "generated_at": "..."}` — all context discarded

3. **Context Builder** (`context_builder.py:140-161`):
   - `ClientContext` dataclass: `client_id`, `profile` (ClientProfile), `summaries` (dict), `raw_data` (dict), `data_freshness` (datetime), `query_intent`, `token_count`
   - `ClientProfile`: `id`, `name`, `abn`, `entity_type`, `industry_code`, `gst_registered`, `revenue_bracket`, `employee_count`, `connection_id`, `last_sync_at`

**Evidence extraction approach**:
- Create a `build_evidence_snapshot()` function that takes `client_context` and `perspective_contexts` and returns a structured dict bounded to 50KB
- Extract key financial metrics: P&L totals, Balance Sheet ratios, AR/AP aging buckets, GST figures, monthly trends
- Each evidence item: `{source: str, period: str, metric: str, value: str}`
- Trim strategy: Remove `extended_data` (fixed assets, POs, journals) first → then `raw_data` → preserve core summaries always

---

## Research Task 2: Frontend UI Patterns for Evidence Display

### Decision: Collapsible evidence sections using existing ExpandableSection pattern + Tooltip for thresholds

### Rationale
The codebase already has well-tested UI primitives for exactly these use cases. The `ExpandableSection` component (`a2ui/layout/ExpandableSection.tsx`) provides the chevron-toggle collapsible pattern with border/bg styling that matches the existing design language. Tooltips from shadcn/ui are already used extensively for metadata display.

### Alternatives Considered
| Alternative | Rejected Because |
|-------------|-----------------|
| Full-page evidence panel (drawer/sheet) | Over-engineered for summary evidence; breaks reading flow |
| Modal dialog for evidence | Blocks interaction; accountants need to compare evidence across options |
| Inline-only (always visible) | Clutters the OPTIONS view; contradicts spec requirement for collapsible |

### Key Findings

**Available UI primitives**:

| Component | Location | Pattern | Use For |
|-----------|----------|---------|---------|
| `ExpandableSection` | `components/a2ui/layout/ExpandableSection.tsx` | ChevronDown rotation, border/bg, children slot | Evidence sections in OptionCard |
| `Tooltip` | `components/ui/tooltip.tsx` | Radix tooltip with TooltipProvider/Trigger/Content | Threshold explanations |
| `Popover` | `components/ui/popover.tsx` | Click-triggered overlay | Richer threshold info |
| `Collapsible` | `components/ui/collapsible.tsx` | Bare Radix re-export | Lower-level collapsible |
| `Accordion` | `components/ui/accordion.tsx` | Multi-section collapsible with mutual exclusion | NOT recommended (evidence sections are independent) |

**Existing citation pattern** (`AgentChatMessage.tsx:217-238`):
- Inline citations rendered as teal pills: `[number]` + truncated title
- No standalone CitationsPanel — citations rendered within message bubble
- Can be extended for data source references

**Quality score pattern** (`QualityScoreCard.tsx:170-198`):
- Label + score + progress bar + description per dimension
- Reusable pattern for confidence breakdowns and threshold displays

**OptionsDisplay current structure** (`OptionsDisplay.tsx`):
- `parseOptions()` regex-parses `### Option X:` into `ParsedOption[]` with `bestIf`, `pros`, `cons`, `action`
- `OptionCard` renders: header → bestIf → pros/cons grid → action footer
- Evidence section insertion point: between action and card bottom
- Props currently: `content: string, optionsCount?, agentsUsed?, generationType?`
- Need to add: `dataSnapshot?: Record<string, unknown>` and `evidence?: EvidenceItem[]`

---

## Research Task 3: API Response & Data Flow Patterns

### Decision: 3-point change to expose `data_snapshot` through the existing model→schema→API→frontend pipeline

### Rationale
The `data_snapshot` JSONB column already exists on the `Insight` model and is populated by `InsightCreate`. The gap is purely in the response serialization: `InsightResponse` omits the field and `_to_response()` doesn't map it. This is a minimal, low-risk change that unblocks all downstream evidence rendering.

### Findings

**Current data flow (broken)**:
```
Insight model (has data_snapshot) → _to_response() (omits it) → InsightResponse (no field) → API JSON (no field) → Frontend Insight type (no field)
```

**Required data flow (fixed)**:
```
Insight model (has data_snapshot) → _to_response() (includes it) → InsightResponse (new field) → API JSON (includes it) → Frontend Insight type (new field)
```

**Exact changes required**:

1. **`schemas.py` line ~84**: Add `data_snapshot: dict[str, Any] | None = None` to `InsightResponse`
2. **`service.py` line ~396**: Add `data_snapshot=insight.data_snapshot` to `InsightResponse()` constructor in `_to_response()`
3. **`frontend/src/types/insights.ts`**: Add `data_snapshot: Record<string, unknown> | null` to `Insight` interface

**Data snapshot population changes**:

4. **`router.py` lines 255-259**: After orchestrator returns, capture `client_context` and `multi_context` into `insight.data_snapshot` before commit
5. **`ai_analyzer.py`**: Replace `{"ai_analysis": True, "generated_at": "..."}` with actual client context dict
6. **`orchestrator.py`**: Return structured context alongside response content (or capture at expand endpoint level)

**Size management**:
- 50KB cap per snapshot (per clarification)
- Trim priority: extended_data first → raw_data → preserve core summaries
- `json.dumps()` size check before storage; trim if exceeds threshold

---

## Research Task 4: Prompt Engineering for Evidence Citations

### Decision: Add `**Evidence:**` field to OPTIONS format template with structured citation instructions

### Rationale
The current `STRATEGY_OPTIONS_SYSTEM_PROMPT` has a well-defined OPTIONS format but no evidence field. Adding an `**Evidence:**` section to the template instructs Claude to cite specific data points inline. Combined with the backend's independent structured evidence extraction, this creates a dual-validation approach.

### Findings

**Current OPTIONS format** (`prompts.py:33-49`):
```
### Option N: [Short Name]
**Best if:** ...
**Pros:** ...
**Cons:** ...
**Action:** ...
```

**Proposed OPTIONS format** (add after `**Action:**`):
```
**Evidence:**
- [Source: P&L FY2025] Revenue: $185,000
- [Source: AR Aging, Feb 2026] Overdue >90 days: $12,400
- [Source: GST Summary Q3] Net GST position: -$4,200
```

**Prompt rules to add**:
- "Every Option MUST include an **Evidence:** section listing the specific financial data points that support the recommendation"
- "Each evidence line MUST reference the data source, reporting period, and specific value"
- "Only cite data that was provided in the context — never fabricate figures"
- "If insufficient data exists for an evidence point, state 'Data not available' rather than omitting"

---

## Research Task 5: Threshold Documentation Patterns

### Decision: Inline tooltips with threshold rules, sourced from a centralized threshold registry

### Rationale
Threshold values are currently hardcoded across multiple analyzer files. Rather than documenting thresholds in each UI component, create a shared registry that both backend (for evaluation) and frontend (for display) can reference.

### Findings

**Hardcoded thresholds identified**:

| Metric | Threshold | Location | Display |
|--------|-----------|----------|---------|
| Quality score dimensions | Weights: reconciliation 30%, freshness 20%, etc. | `quality/service.py` | No transparency |
| BAS variance severity | Critical >50% or >$10K; Warning >20% or >$5K | `insights/analyzers/variance_analyzer.py` | Severity badge, no explanation |
| AR aging risk | High >30% overdue, Medium >15% | `insights/analyzers/ai_analyzer.py` | Risk label only |
| Balance sheet health | Current ratio <1.0 = danger, <1.5 = warning | `insights/analyzers/ai_analyzer.py` | Color indicator only |
| GST early warning | $65K threshold approaching | `insights/analyzers/compliance_analyzer.py` | Alert, no threshold shown |
| Cash flow trend | 3 consecutive months negative | `insights/analyzers/ai_analyzer.py` | Alert, no methodology |
| Data staleness | 7 days (per clarification) | New (platform-wide) | No indicator currently |

**Approach**: Create a `ThresholdRegistry` (Python dict/dataclass) that maps metric→thresholds→labels. Expose via a lightweight API endpoint (`GET /api/v1/platform/thresholds`) for frontend to consume and render in tooltips.
