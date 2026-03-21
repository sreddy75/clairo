# Tasks: Platform-Wide Evidence & Traceability

**Input**: Design documents from `/specs/044-insight-evidence-traceability/`
**Prerequisites**: plan.md (required), spec.md (required), research.md, data-model.md, contracts/

**Tests**: Not explicitly requested — test tasks omitted. Tests should be added as part of implementation where appropriate.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story. User stories are grouped by deployment phase (P1, P2, P3) as per rollout strategy.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

## Path Conventions

- **Web app**: `backend/app/` (Python), `frontend/src/` (TypeScript)

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/044-insight-evidence-traceability`
  - Verify: You are now on the feature branch

---

## Phase 1: Foundational (Blocking Prerequisites)

**Purpose**: Shared Pydantic schemas and evidence extraction logic that all P1 user stories depend on

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T001 Create evidence Pydantic schemas in `backend/app/modules/insights/evidence.py`
  - Define `EvidenceItem` model: `source` (str), `period` (str), `metric` (str), `value` (str), `category` (Literal["financial", "aging", "gst", "quality", "trend"])
  - Define `DataSnapshotV1` model: `version` (str, default "1.0"), `captured_at` (datetime), `data_freshness` (datetime | None), `evidence_items` (list[EvidenceItem]), `profile` (dict | None), `financial_summary` (dict | None), `aging_summary` (dict | None), `gst_summary` (dict | None), `monthly_trends` (list[dict] | None), `quality_scores` (dict | None), `perspectives_used` (list[str]), `ai_analysis` (bool, default True), `generated_at` (str)
  - Ref: data-model.md for field definitions, contracts/insight-evidence-api.yaml for schema

- [x] T002 Implement `build_evidence_snapshot()` function in `backend/app/modules/insights/evidence.py`
  - Takes `client_context` (ClientContext from context_builder.py) and `perspective_contexts` (dict) as inputs
  - Extracts structured evidence items from known financial data:
    - From P&L report context → revenue, expenses, net profit evidence items
    - From Balance Sheet → current ratio, debt-to-equity evidence items
    - From AR/AP aging → overdue amounts, aging bucket evidence items
    - From GST summary → collected, paid, net position evidence items
    - From monthly trends → trend direction evidence items
    - From quality scores → score breakdown evidence items
  - Returns `DataSnapshotV1` model with all evidence items and summary sections
  - Ref: research.md "Evidence Extraction Patterns" for data shapes

- [x] T003 Implement `trim_snapshot_to_size()` function in `backend/app/modules/insights/evidence.py`
  - Takes a `DataSnapshotV1` model and max size (default 50KB)
  - Serializes to JSON and checks size
  - If over limit, trim in priority order: (1) remove extended_data, (2) truncate monthly_trends to 3 months, (3) remove raw_data, (4) always preserve core summaries
  - Returns trimmed snapshot dict suitable for JSONB storage
  - Ref: data-model.md "Size Constraint" section

- [x] T004 Add `data_snapshot` field to `InsightResponse` in `backend/app/modules/insights/schemas.py`
  - Add `data_snapshot: dict[str, Any] | None = None` to `InsightResponse` class (after `confidence` field, line ~84)
  - No changes to `InsightCreate` (already has `data_snapshot`)
  - Ref: contracts/insight-evidence-api.yaml InsightResponseV2

- [x] T005 Include `data_snapshot` in `_to_response()` method in `backend/app/modules/insights/service.py`
  - Add `data_snapshot=insight.data_snapshot` to the `InsightResponse()` constructor in `_to_response()` (line ~396)
  - This is the sole serialization gateway — all insight API responses flow through this method

**Checkpoint**: Foundation ready — evidence schemas, extraction logic, and API response pipeline are in place

---

## Phase 2: User Story 1 — Evidence Behind Insight Analysis Options (Priority: P1) 🎯 MVP

**Goal**: Each expanded insight option includes structured evidence items with data source references. Accountants can see what data backs each AI recommendation.

**Independent Test**: Expand any insight via POST `/api/v1/insights/{id}/expand`, verify each option includes evidence items in `data_snapshot.evidence_items` with source, period, metric, value fields.

### Implementation for User Story 1

- [x] T006 [US1] Add `**Evidence:**` field to OPTIONS format template in `backend/app/modules/agents/prompts.py`
  - In `STRATEGY_OPTIONS_SYSTEM_PROMPT`, add after the `**Action:**` line in the Required Format section:
    ```
    **Evidence:**
    - [Source: P&L FY2025] Revenue: $185,000
    - [Source: AR Aging, Feb 2026] Overdue >90 days: $12,400
    ```
  - Add rules: "Every Option MUST include an **Evidence:** section listing specific financial data points that support the recommendation", "Each evidence line MUST reference the data source, reporting period, and specific value", "Only cite data provided in the context — never fabricate figures"
  - Ref: research.md "Prompt Engineering for Evidence Citations"

- [x] T007 [US1] Modify orchestrator to expose structured context in `backend/app/modules/agents/orchestrator.py`
  - In `process_query()` method (line ~240), modify the return to also expose `client_context` and `perspective_contexts` alongside the existing `OrchestratorResponse`
  - Option A: Add `client_context` and `perspective_contexts` fields to `OrchestratorResponse` in `backend/app/modules/agents/schemas.py`
  - Option B: Return a tuple/named result from `process_query()` with both content and raw context
  - The goal is to make the structured data available to the calling expand endpoint without modifying the orchestrator's core logic
  - Ref: orchestrator.py lines 250-272 where `client_context` and `multi_context` are built

- [x] T008 [US1] Modify expand endpoint to capture evidence snapshot in `backend/app/modules/insights/router.py`
  - In `expand_insight()` (lines 199-264), after orchestrator returns:
    1. Call `build_evidence_snapshot(client_context, perspective_contexts)` from `evidence.py`
    2. Call `trim_snapshot_to_size()` to enforce 50KB cap
    3. Set `insight.data_snapshot = trimmed_snapshot`
  - The snapshot captures what data was available BEFORE prompt construction
  - Ensure the snapshot includes `captured_at` timestamp and `data_freshness` from client_context
  - Must work for both manual expansion and proactive Magic Zone

- [x] T009 [US1] Add `data_snapshot` to frontend `Insight` type in `frontend/src/types/insights.ts`
  - Add `data_snapshot?: Record<string, unknown> | null` to the `Insight` interface
  - Add `EvidenceItem` type: `{ source: string; period: string; metric: string; value: string; category: 'financial' | 'aging' | 'gst' | 'quality' | 'trend' }`
  - Add `DataSnapshot` type with `evidence_items?: EvidenceItem[]`, `data_freshness?: string`, `captured_at?: string`, `profile?: Record<string, unknown>`

**Checkpoint**: User Story 1 backend complete — expand endpoint returns evidence in data_snapshot. Frontend type ready.

---

## Phase 3: User Story 2 — Collapsible Evidence Display (Priority: P1)

**Goal**: Evidence items render as collapsible sections within each option card, collapsed by default.

**Independent Test**: Expand an insight in the UI, verify each option card shows "X data points" collapsed indicator. Click to expand and see evidence items. Click again to collapse.

### Implementation for User Story 2

- [x] T010 [P] [US2] Create `EvidenceSection` component in `frontend/src/components/insights/EvidenceSection.tsx`
  - Create a collapsible evidence display component following the `ExpandableSection` pattern from `frontend/src/components/a2ui/layout/ExpandableSection.tsx`
  - Props: `evidence: EvidenceItem[]` (from data_snapshot.evidence_items)
  - Collapsed state: Show count indicator (e.g., "3 data points" with a ChevronDown icon)
  - Expanded state: Render each evidence item as a row: `[category icon] source · period — metric: value`
  - Group evidence items by category (financial, aging, gst, quality, trend) with subtle category headers
  - Collapsed by default per FR-004
  - Graceful degradation: If `evidence` is empty/undefined, show "No evidence data available" per FR-005
  - Use existing Tailwind utility classes and border/bg styling from ExpandableSection

- [x] T011 [US2] Integrate `EvidenceSection` into `OptionsDisplay` in `frontend/src/components/insights/OptionsDisplay.tsx`
  - Import `EvidenceSection` component
  - Accept new prop `dataSnapshot?: DataSnapshot` on `OptionsDisplay`
  - In the `OptionCard` component, after the action section (line ~177), add `<EvidenceSection evidence={dataSnapshot?.evidence_items ?? []} />`
  - Map evidence items to the correct option if possible, or show all evidence items per card
  - Pass `dataSnapshot` from `InsightDetailPanel` through to `OptionsDisplay`

- [x] T012 [US2] Wire `data_snapshot` through `InsightDetailPanel` in `frontend/src/components/insights/InsightDetailPanel.tsx`
  - The `InsightDetailPanel` receives the full `Insight` object
  - Pass `insight.data_snapshot` to `OptionsDisplay` as a new prop
  - Verify the data flows from API response → TanStack Query cache → InsightDetailPanel → OptionsDisplay → EvidenceSection

**Checkpoint**: User Story 2 complete — evidence sections visible in option cards, collapsible, graceful degradation for legacy insights

---

## Phase 4: User Story 3 — Data Snapshot Preservation for Audit Trail (Priority: P1)

**Goal**: All AI-generated insights store the financial context used during analysis, creating an immutable audit trail.

**Independent Test**: Expand an insight, then GET the insight via API and verify `data_snapshot` contains structured financial context (not just `{"ai_analysis": True}`). Compare with a pre-existing insight that should still have the old stub.

### Implementation for User Story 3

- [x] T013 [US3] Update AI Analyzer to store real context in `backend/app/modules/insights/analyzers/ai_analyzer.py`
  - In the insight creation block (line ~563), replace `data_snapshot={"ai_analysis": True, "generated_at": datetime.now(UTC).isoformat()}` with a call to `build_evidence_snapshot()` using the client context dict built by `_build_client_context()`
  - Import `build_evidence_snapshot` and `trim_snapshot_to_size` from `evidence.py`
  - The `_build_client_context()` method already builds a comprehensive dict — pass it to `build_evidence_snapshot()` adapted for the AI Analyzer context shape
  - Ensure `trim_snapshot_to_size()` is called to enforce 50KB cap
  - Preserve `ai_analysis: True` and `generated_at` in the snapshot for backward compatibility

- [x] T014 [US3] Update Magic Zone analyzer snapshot storage in `backend/app/modules/insights/analyzers/magic_zone.py`
  - Find the insight creation code (around line 468) and ensure it captures the financial context used during Magic Zone analysis
  - Apply the same pattern as T013: call `build_evidence_snapshot()` with available context, trim to size, store in `data_snapshot`
  - The Magic Zone analyzer uses the orchestrator's context — ensure the snapshot captures what was sent to the LLM

- [x] T015 [US3] Handle backward compatibility for legacy insights without snapshots
  - In `_to_response()` in `service.py`: `data_snapshot` for pre-existing insights will be `None` or `{"ai_analysis": True}` — this is fine, frontend handles graceful degradation (T010 FR-005)
  - Verify that the API response correctly returns `null` for insights with no snapshot and the old stub dict for insights with the legacy stub
  - No migration needed — this is purely about ensuring new code doesn't break with old data

**Checkpoint**: User Story 3 complete — all new AI insights store full context snapshots. Legacy insights return their existing data_snapshot (null or stub).

---

## Phase 5: Hide Confidence Scores (FR-026a, bundled with P1)

**Goal**: Remove meaningless hardcoded confidence display from UI until P3 reforms it.

**Independent Test**: View any insight in the UI — confidence score should not be visible anywhere. API response still includes confidence field (backend unchanged).

- [x] T016 [US1] Hide confidence score display in frontend insight components
  - Search `frontend/src/components/insights/` for any rendering of `confidence` field — as of audit, no confidence display exists in `InsightDetailPanel.tsx` or `OptionsDisplay.tsx`
  - Search `frontend/src/components/` more broadly for `insight.confidence` or `confidence` rendering in insight contexts
  - If found: wrap in a comment or remove. If not found: document that confidence was never rendered (no action needed beyond confirming)
  - Do NOT remove `confidence` from the `Insight` type or `InsightResponse` schema — backend storage continues unchanged

**Checkpoint**: P1 complete — Evidence in OPTIONS, collapsible display, data snapshots, confidence hidden

---

## Phase 6: User Story 4 — Agent Chat Citation Consistency (Priority: P2)

**Goal**: The Agent Orchestrator includes inline citation markers in responses, consistent with existing Knowledge Chatbot citation format.

**Independent Test**: Ask the AI assistant a client-specific financial question. Verify response contains inline citation markers like `[Data: AR Aging, Feb 2026]` or `[Source: ATO GST Guide]`.

### Implementation for User Story 4

- [x] T017 [P] [US4] Add citation instructions to Agent Orchestrator system prompt in `backend/app/modules/agents/prompts.py`
  - In the multi-perspective system prompt builder, add instructions:
    - "When referencing financial data, include inline citation markers: `[Data: Source Name, Period]`"
    - "When referencing knowledge base content, include inline citation markers: `[Source: Document Title]`"
    - "Citation markers must be specific — never use generic [Source: data] markers"
  - Ensure consistency with any existing citation instructions in the Knowledge Chatbot prompts
  - Ref: FR-012 to FR-015

- [x] T018 [P] [US4] Propagate knowledge base source URLs in orchestrator response in `backend/app/modules/agents/orchestrator.py`
  - When knowledge chunks are included in context, ensure the source URL from vector store metadata is preserved in the response
  - Currently knowledge chunks have metadata (title, URL) but this may not flow to the citation rendering
  - Ensure `knowledge_chunks` metadata is included in the orchestrator response citations list

- [x] T019 [US4] Enhance citation rendering in `frontend/src/components/assistant/AgentChatMessage.tsx`
  - Review existing inline citation pill rendering (lines 217-238)
  - Ensure citation markers from AI responses (e.g., `[Data: AR Aging, Feb 2026]`) are parsed and rendered as interactive elements
  - Add hover/click to show source detail: title, URL (if knowledge base), data source name (if financial data)
  - Ensure consistent rendering across Knowledge Chatbot, Client Chatbot, and Agent Orchestrator message types

**Checkpoint**: User Story 4 complete — Agent chat responses include inline citations, interactive on hover/click

---

## Phase 7: User Story 5 — Data Freshness Indicators (Priority: P2)

**Goal**: All AI-generated content shows "Data as of [date]" indicator, with stale data warnings (>7 days).

**Independent Test**: Select a client with stale data, view an expanded insight or ask the AI assistant a question. Verify "Data as of" indicator and "Stale data" warning appear alongside the content.

### Implementation for User Story 5

- [x] T020 [P] [US5] Create `DataFreshnessIndicator` component in `frontend/src/components/insights/DataFreshnessIndicator.tsx`
  - Props: `lastSyncDate: string | null`, `staleDaysThreshold?: number` (default 7)
  - Normal state: Subtle "Data as of [formatted date]" badge (e.g., "Data as of 20 Feb 2026")
  - Stale state: Prominent amber/orange warning badge "Data may be stale — last synced [X] days ago"
  - No date: Show "Data freshness unknown"
  - Use existing badge/pill styling from shadcn/ui

- [x] T021 [US5] Integrate freshness indicator into `InsightDetailPanel` in `frontend/src/components/insights/InsightDetailPanel.tsx`
  - Import `DataFreshnessIndicator`
  - For expanded insights: Use `insight.data_snapshot?.data_freshness` as the date source (FR-018)
  - For non-expanded insights: Use the client's last sync date if available from client context
  - Place indicator near the top of the detail panel, below the priority/category badges

- [x] T022 [US5] Integrate freshness indicator into AI chat responses in `frontend/src/components/assistant/AgentChatMessage.tsx`
  - For responses that reference client financial data, include a `DataFreshnessIndicator` below the message
  - The freshness date should come from the chat response metadata (may need to propagate `data_freshness` from orchestrator response)
  - If orchestrator doesn't currently return data freshness: Add `data_freshness` field to the chat response schema in `backend/app/modules/agents/schemas.py` (OrchestratorResponse)

**Checkpoint**: User Story 5 complete — freshness indicators on insights and chat responses, stale warnings prominent

---

## Phase 8: User Story 6 — Threshold Transparency (Priority: P2)

**Goal**: All computed scores and severity classifications show their methodology/thresholds via tooltips.

**Independent Test**: Hover over a quality score badge, BAS variance severity label, balance sheet health indicator, or AR risk badge. Verify a tooltip appears explaining the threshold rules.

### Implementation for User Story 6

- [x] T023 [P] [US6] Create threshold registry in `backend/app/modules/insights/thresholds.py`
  - Define `ThresholdBand` Pydantic model: `label` (str), `color` (str), `condition` (str)
  - Define `ThresholdRule` Pydantic model: `metric_key` (str), `display_name` (str), `rules` (list[ThresholdBand]), `description` (str)
  - Create `THRESHOLD_REGISTRY: list[ThresholdRule]` containing all platform thresholds:
    - `quality_score`: Dimension weights (Freshness 20%, Reconciliation 30%, Completeness 25%, Timeliness 25%) with note that reconciliation is a proxy for authorisation status
    - `bas_variance_severity`: Critical (>50% or >$10K), Warning (>20% or >$5K), Info (any change)
    - `balance_sheet_current_ratio`: Danger (<1.0), Warning (<1.5), Healthy (≥1.5), benchmark 1.5-2.0
    - `balance_sheet_debt_equity`: High (>2.0), Moderate (>1.0), Low (≤1.0)
    - `ar_risk`: High (>30% overdue), Medium (>15%), Low (≤15%)
    - `gst_registration_threshold`: $75K annual turnover (mandatory GST registration)
    - `gst_early_warning`: Approaching $65K
    - `cash_flow_trend`: 3 consecutive months negative = alert
    - `data_staleness`: >7 days = stale
  - Ref: research.md "Threshold Documentation Patterns"

- [x] T024 [P] [US6] Add thresholds API endpoint in `backend/app/modules/insights/router.py`
  - Add `GET /api/v1/platform/thresholds` endpoint
  - Returns `ThresholdRegistryResponse` containing the full `THRESHOLD_REGISTRY` list
  - No auth required beyond standard tenant authentication (thresholds are platform-wide, not tenant-specific)
  - Ref: contracts/insight-evidence-api.yaml ThresholdRegistryResponse

- [x] T025 [P] [US6] Create `ThresholdTooltip` component in `frontend/src/components/insights/ThresholdTooltip.tsx`
  - Props: `metricKey: string` (maps to threshold registry), `children: ReactNode` (the badge/label to wrap)
  - Fetches threshold data from `GET /api/v1/platform/thresholds` (cache with TanStack Query, staleTime: Infinity since thresholds are static)
  - Renders a Tooltip (from `components/ui/tooltip.tsx`) wrapping children
  - Tooltip content: Display name, description, and threshold bands as a compact list: "Critical: >50% change or >$10K" / "Warning: >20% or >$5K" etc.
  - If threshold data not loaded, render children without tooltip (graceful degradation)

- [x] T026 [US6] Integrate threshold tooltips into quality score displays
  - In `frontend/src/components/quality/QualityScoreCard.tsx`: Wrap the overall score badge with `<ThresholdTooltip metricKey="quality_score">` showing dimension weights
  - In dimension breakdown rows (lines 170-198): Add info icon next to "Reconciliation" dimension with tooltip noting it's a proxy for authorisation status

- [x] T027 [US6] Integrate threshold tooltips into variance and risk displays
  - Find BAS variance severity badges in `frontend/src/components/` — wrap with `<ThresholdTooltip metricKey="bas_variance_severity">`
  - Find balance sheet health indicators — wrap current ratio with `<ThresholdTooltip metricKey="balance_sheet_current_ratio">`
  - Find AR/AP risk labels — wrap with `<ThresholdTooltip metricKey="ar_risk">`
  - Each integration is a minimal change: wrap existing badge/label JSX with ThresholdTooltip

- [x] T028 [US6] Add threshold context to insight generation text per FR-023
  - In insight detail text generated by analyzers: when a threshold triggers an insight (e.g., GST $65K warning, AR 30% overdue), include the threshold value in the insight detail text
  - Check `backend/app/modules/insights/analyzers/compliance.py` for GST threshold insights
  - Check `backend/app/modules/insights/analyzers/ai_analyzer.py` for AR/cash flow threshold insights
  - Add explicit threshold mention: "This alert triggered because [metric] exceeded the [threshold] threshold"

**Checkpoint**: P2 complete — Chat citations consistent, freshness indicators everywhere, threshold transparency via tooltips

---

## Phase 9: User Story 7 — Meaningful Confidence Scores (Priority: P3)

**Goal**: Confidence scores reflect actual data quality rather than hardcoded constants. Breakdown accessible to accountants.

**Independent Test**: Generate insights for two clients — one with full Xero data, one with minimal data. Verify confidence scores differ meaningfully. Click confidence indicator to see breakdown.

### Implementation for User Story 7

- [x] T029 [P] [US7] Implement confidence calculation service in `backend/app/modules/insights/evidence.py`
  - Create `calculate_confidence()` function that takes:
    - `data_snapshot: DataSnapshotV1` (evidence completeness)
    - `data_freshness: datetime | None` (recency)
    - `knowledge_chunks_count: int` (RAG match quality)
    - `perspectives_used: list[str]` (coverage breadth)
  - Returns `ConfidenceBreakdown` dict: `overall` (0-1), `data_completeness` (0-1), `data_freshness` (0-1), `knowledge_match` (0-1), `perspective_coverage` (0-1)
  - `data_completeness`: Based on how many snapshot sections are non-null (profile, financial, aging, gst, trends, quality)
  - `data_freshness`: 1.0 if synced today, decays linearly to 0.3 at 30 days, floors at 0.1
  - `knowledge_match`: Based on chunk count — 0 chunks = 0.3, 1-3 = 0.6, 4+ = 0.9
  - `perspective_coverage`: number of perspectives used / total available perspectives
  - `overall`: Weighted average (completeness 40%, freshness 25%, knowledge 20%, coverage 15%)

- [x] T030 [US7] Replace hardcoded confidence values across all analyzers
  - `backend/app/modules/insights/analyzers/ai_analyzer.py` line 562: Replace `confidence=float(data.get("confidence", 0.75))` with `calculate_confidence()` call
  - `backend/app/modules/insights/analyzers/magic_zone.py` line 468: Replace `confidence=0.85` with calculated value
  - `backend/app/modules/insights/service.py` lines 445, 487, 501: Replace hardcoded values with appropriate calculations
  - Rule-based analyzers (quality.py, cashflow.py, compliance.py, journal_anomaly.py): These can keep high confidence (0.85-0.95) since they use deterministic rules, but add `data_freshness` factor
  - Store `confidence_breakdown` in `data_snapshot` for frontend display

- [x] T031 [US7] Create confidence breakdown display component in `frontend/src/components/insights/ConfidenceBreakdown.tsx`
  - Props: `confidence: number`, `breakdown?: { data_completeness: number, data_freshness: number, knowledge_match: number, perspective_coverage: number }`
  - Display: Confidence score badge (color-coded: green ≥0.7, amber ≥0.4, red <0.4)
  - On hover/click: Popover showing breakdown factors using the QualityScoreCard dimension pattern (label + progress bar + description)
  - If no breakdown available (legacy insights): Show score only, no interactive breakdown

- [x] T032 [US7] Re-enable confidence display in insight components
  - In `InsightDetailPanel.tsx`: Add `ConfidenceBreakdown` component, now showing meaningful calculated scores
  - In `OptionsDisplay.tsx`: Optionally show confidence in the header area of expanded insights
  - This reverses the hiding done in T016 — but only after confidence is meaningful

**Checkpoint**: User Story 7 complete — confidence scores meaningful, breakdown accessible

---

## Phase 10: User Story 8 — Safe AI Content Export (Priority: P3)

**Goal**: All AI content exports include appropriate disclaimers, data freshness, and confidence metadata.

**Independent Test**: Click "Email" on an AI chat response — verify email body includes disclaimer, data freshness, confidence. Click "Copy" — verify clipboard includes same caveats.

### Implementation for User Story 8

- [x] T033 [P] [US8] Create export enrichment utility in `frontend/src/lib/ai-export-utils.ts`
  - `enrichAIContentForExport(content: string, metadata: { dataFreshness?: string, confidence?: number, isEscalated?: boolean }): string`
  - Prepends/appends:
    - Header: "AI-generated analysis — verify before relying on"
    - Data freshness: "Data as of: [date]"
    - Confidence: "Analysis confidence: [X]%"
    - If escalated: "⚠️ Professional review recommended: [escalation reason]"
    - Footer: "Generated by Clairo AI. This analysis is for informational purposes only and should be verified by a qualified professional before use."

- [x] T034 [US8] Integrate export enrichment into email action
  - Find the email export handler for AI chat responses (likely in `frontend/src/components/assistant/` or action handlers)
  - Before sending email, call `enrichAIContentForExport()` to wrap the content with caveats
  - Ensure the email includes all metadata: disclaimer, freshness, confidence per FR-027

- [x] T035 [US8] Integrate export enrichment into copy-to-clipboard action
  - Find the copy handler for AI responses
  - Before copying to clipboard, call `enrichAIContentForExport()` to append caveats as footer per FR-028
  - Ensure escalated responses include "Professional review recommended" per FR-029

**Checkpoint**: User Story 8 complete — all exports include safety metadata

---

## Phase 11: Mock Data Safety (FR-030, bundled with P3)

**Goal**: Any UI component falling back to mock/sample data shows a "Sample Data" watermark.

**Independent Test**: Trigger a mock data fallback in any A2UI visualization. Verify "Sample Data" watermark is visible.

- [x] T036 [US8] Audit A2UI components for mock data fallbacks in `frontend/src/components/a2ui/`
  - Search for hardcoded mock/sample data arrays, `mockData`, `sampleData`, `placeholder` data in A2UI visualization components
  - For each component that falls back to mock data: Add a visible "Sample Data" watermark overlay
  - Watermark: Semi-transparent overlay text "SAMPLE DATA" diagonally across the visualization, or a prominent banner above it
  - Ensure fabricated financial figures are never displayed as real client data

**Checkpoint**: P3 complete — meaningful confidence, safe exports, no invisible mock data

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that span multiple user stories

- [x] T037 [P] Add audit event logging for insight expansion in `backend/app/modules/insights/router.py`
  - After successful expansion (T008): Emit `insight.expanded` audit event with insight_id, tenant_id, client_id, perspectives_used, evidence_count
  - After snapshot storage: Emit `insight.snapshot_stored` with insight_id, snapshot_size_bytes, data_sources_included
  - Use existing audit infrastructure from `app.core.audit`
  - Ref: spec.md "Audit Implementation Requirements" table

- [x] T038 [P] Verify backward compatibility with existing insights
  - Test that insights created before this feature (with `data_snapshot: null` or `{"ai_analysis": True}`) still render correctly in the UI
  - Test that the `InsightListResponse` (paginated list) works with mixed old/new insights
  - Test that evidence section shows "No evidence data available" for legacy insights

- [x] T039 Run quickstart.md validation
  - Follow the verification steps in `specs/044-insight-evidence-traceability/quickstart.md`
  - Verify P1 backend flow: expand → evidence in response
  - Verify P1 frontend flow: option cards → collapsible evidence
  - Verify P2 flow: chat citations, freshness indicators, threshold tooltips
  - Verify P3 flow: confidence breakdown, export caveats, mock data watermark

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [x] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest`
  - Run: `cd frontend && npm run lint`
  - All tests must pass before PR

- [x] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check .`
  - Run: `cd frontend && npm run lint`
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/044-insight-evidence-traceability`
  - Run: `gh pr create --title "Spec 044: Platform-Wide Evidence & Traceability" --body "..."`
  - Include summary of changes per phase in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 044 as COMPLETE
  - Update current focus to next spec

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first
- **Foundational (Phase 1)**: Depends on Phase 0 — BLOCKS all user stories
- **US1 Evidence (Phase 2)**: Depends on Phase 1 (needs evidence schemas + API response changes)
- **US2 Collapsible Display (Phase 3)**: Depends on Phase 2 (needs evidence data flowing to frontend)
- **US3 Snapshot Preservation (Phase 4)**: Depends on Phase 1 (needs evidence.py). Can run in PARALLEL with Phase 2-3 (different files)
- **Hide Confidence (Phase 5)**: Independent — can run any time after Phase 0
- **US4 Chat Citations (Phase 6)**: Independent of P1 — can start after Phase 1
- **US5 Freshness (Phase 7)**: Depends on Phase 4 (needs data_freshness in snapshots)
- **US6 Thresholds (Phase 8)**: Independent — can run in parallel with Phases 6-7
- **US7 Confidence Reform (Phase 9)**: Depends on Phase 1 (needs evidence.py for calculation). Comes after P2.
- **US8 Export Safety (Phase 10)**: Depends on Phase 9 (needs confidence values)
- **Mock Data Safety (Phase 11)**: Independent — can run any time
- **Polish (Phase 12)**: Depends on all desired phases being complete

### User Story Dependencies

```
Phase 0 (Git) → Phase 1 (Foundation)
                    ├── Phase 2 (US1: Evidence) → Phase 3 (US2: Collapsible) ─┐
                    ├── Phase 4 (US3: Snapshots) ─────────────────────────────┤─── P1 Complete
                    ├── Phase 5 (Hide Confidence) ────────────────────────────┘
                    │
                    ├── Phase 6 (US4: Chat Citations) ────────────────────────┐
                    ├── Phase 7 (US5: Freshness) ─────────────────────────────┤─── P2 Complete
                    ├── Phase 8 (US6: Thresholds) ────────────────────────────┘
                    │
                    ├── Phase 9 (US7: Confidence Reform) ─────────────────────┐
                    ├── Phase 10 (US8: Export Safety) ────────────────────────┤─── P3 Complete
                    └── Phase 11 (Mock Data Safety) ──────────────────────────┘
```

### Parallel Opportunities

**Within P1** (after Foundation):
- T006, T007 can run in parallel (different files: prompts.py vs orchestrator.py)
- T009, T010 can run in parallel (different files: insights.ts vs EvidenceSection.tsx)
- T013, T014 can run in parallel (different analyzer files)

**Across P2** (after P1 complete):
- T017, T020, T023, T024, T025 can ALL run in parallel (all different files)

**Across P3**:
- T029, T033 can run in parallel (different files: evidence.py vs ai-export-utils.ts)

---

## Parallel Example: P1 MVP

```bash
# After Foundation (T001-T005) completes:

# Parallel group A (backend, different files):
Task T006: "Add Evidence field to OPTIONS prompt in prompts.py"
Task T007: "Modify orchestrator to expose structured context in orchestrator.py"

# Sequential (depends on T006+T007):
Task T008: "Modify expand endpoint to capture evidence snapshot in router.py"

# Parallel group B (frontend, different files):
Task T009: "Add data_snapshot to frontend Insight type in insights.ts"
Task T010: "Create EvidenceSection component in EvidenceSection.tsx"

# Sequential (depends on T009+T010):
Task T011: "Integrate EvidenceSection into OptionsDisplay"
Task T012: "Wire data_snapshot through InsightDetailPanel"
```

---

## Implementation Strategy

### MVP First (P1 Only — US1 + US2 + US3 + Hide Confidence)

1. Complete Phase 0: Git Setup
2. Complete Phase 1: Foundation (evidence.py schemas, InsightResponse, _to_response)
3. Complete Phase 2: US1 Evidence in OPTIONS (prompt + orchestrator + expand endpoint)
4. Complete Phase 3: US2 Collapsible Display (EvidenceSection + integration)
5. Complete Phase 4: US3 Snapshot Preservation (AI Analyzer + Magic Zone)
6. Complete Phase 5: Hide Confidence
7. **STOP and VALIDATE**: Test P1 independently — expand insights, verify evidence + snapshots
8. Deploy P1

### Incremental Delivery

1. **P1 ships** → Evidence + snapshots + confidence hidden (core trust + audit)
2. **P2 ships** → Chat citations + freshness + thresholds (platform transparency)
3. **P3 ships** → Confidence reform + export safety + mock data (quality-of-life)

Each phase independently deployable per rollout strategy.

---

## Summary

| Metric | Count |
|--------|-------|
| **Total tasks** | 39 + 6 final = 45 |
| **P1 tasks (US1 + US2 + US3 + confidence)** | 16 (T001-T016) |
| **P2 tasks (US4 + US5 + US6)** | 12 (T017-T028) |
| **P3 tasks (US7 + US8 + mock data)** | 8 (T029-T036) |
| **Polish + Final** | 9 (T037-T039 + TFINAL) |
| **New backend files** | 2 (evidence.py, thresholds.py) |
| **New frontend components** | 5 (EvidenceSection, DataFreshnessIndicator, ThresholdTooltip, ConfidenceBreakdown, ai-export-utils) |
| **Modified backend files** | 7 (schemas.py, service.py, router.py, prompts.py, orchestrator.py, ai_analyzer.py, magic_zone.py) |
| **Modified frontend files** | 4 (insights.ts, OptionsDisplay.tsx, InsightDetailPanel.tsx, AgentChatMessage.tsx) |
| **Database migrations** | 0 |
| **Breaking API changes** | 0 |

## Notes

- [P] tasks = different files, no dependencies — safe for parallel execution
- [Story] label maps task to specific user story for traceability
- Each P1/P2/P3 phase is independently deployable
- Commit after each task or logical group
- Stop at any checkpoint to validate phase independently
