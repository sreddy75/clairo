# Implementation Plan: Platform-Wide Evidence & Traceability

**Branch**: `044-insight-evidence-traceability` | **Date**: 2026-02-24 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/044-insight-evidence-traceability/spec.md`

## Summary

Add evidence traceability to all AI-generated content across the Clairo platform. A platform-wide audit identified 28 transparency gaps across 5 systemic root causes. This feature addresses them in 3 phases: P1 adds structured evidence to Insight OPTIONS and preserves financial context as data snapshots (audit trail); P2 extends transparency to agent chat citations, data freshness indicators, and threshold methodology tooltips; P3 reforms confidence scores, adds export safety disclaimers, and enforces mock data watermarks.

The technical approach uses **hybrid evidence extraction**: the backend independently extracts structured evidence from the known financial context (before it is flattened into a prompt), while the AI is additionally instructed to include inline citations for human readability. The frontend renders evidence exclusively from the structured backend data — never by parsing AI markdown.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, anthropic SDK, Next.js 14, shadcn/ui, TanStack Query, Zustand
**Storage**: PostgreSQL 16 (existing `data_snapshot` JSONB column on `insights` table — no migration needed)
**Testing**: pytest + pytest-asyncio (backend), Jest/Vitest (frontend)
**Target Platform**: Web application (Next.js frontend + FastAPI backend)
**Project Type**: Web application (frontend + backend)
**Performance Goals**: Evidence display adds <1s to insight detail panel render; snapshot extraction <500ms; 50KB max snapshot size
**Constraints**: No breaking API changes; backwards-compatible with existing insights; 7-year audit retention for snapshots
**Scale/Scope**: ~28 transparency gaps across 8 user stories, 30 functional requirements, 3 deployment phases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith structure | PASS | All changes within existing modules (`insights`, `agents`, `knowledge`). No new modules created. |
| Module boundaries | PASS | Cross-module access via service layer only. Evidence extraction uses existing `context_builder` service. |
| Repository pattern for DB access | PASS | Snapshot storage via existing `InsightService` repository methods. No direct cross-module DB queries. |
| Multi-tenancy (tenant_id isolation) | PASS | No new tables. Existing RLS on `insights` table covers snapshots. |
| Audit-first | PASS | Feature explicitly adds audit trail (data snapshots). Audit events defined in spec: `insight.expanded`, `insight.snapshot_stored`, `ai.response_generated`. |
| Type hints everywhere | PASS | All new Python code uses type hints. New Pydantic schemas for evidence items. |
| Pydantic for all schemas | PASS | `EvidenceItem`, `DataSnapshot`, `ThresholdRule` all as Pydantic models. |
| Async/await for all I/O | PASS | All existing endpoints are async. No sync I/O introduced. |
| Domain exceptions (not HTTPException in services) | PASS | No new service-layer exceptions needed. Evidence extraction is pure data transformation. |
| Testing (80% unit, 100% integration) | PASS | Test plan covers unit tests for evidence extraction, integration tests for expand endpoint, frontend component tests. |
| Human-in-the-loop for AI | PASS | Feature adds transparency TO human review; does not change approval flow. |
| Source citations on all answers (L3 standard) | PASS | This feature IMPLEMENTS this constitution requirement for insights and agent chat. |
| AI outputs clearly labeled | PASS | Export safety (P3) adds disclaimers to all AI content exports. |

**Post-Phase 1 re-check**: All gates still pass. No new modules, no new tables, no breaking changes.

## Project Structure

### Documentation (this feature)

```text
specs/044-insight-evidence-traceability/
├── plan.md              # This file
├── research.md          # Phase 0 output — research findings
├── data-model.md        # Phase 1 output — entity definitions
├── quickstart.md        # Phase 1 output — developer guide
├── contracts/           # Phase 1 output — API contract changes
│   └── insight-evidence-api.yaml
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (NOT created by /speckit.plan)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── insights/
│   │   │   ├── schemas.py         # MODIFY: Add data_snapshot to InsightResponse
│   │   │   ├── service.py         # MODIFY: Include data_snapshot in _to_response()
│   │   │   ├── router.py          # MODIFY: Capture context in expand endpoint; add thresholds endpoint
│   │   │   ├── evidence.py        # NEW: Evidence extraction + snapshot builder
│   │   │   └── thresholds.py      # NEW (P2): Threshold registry
│   │   ├── agents/
│   │   │   ├── prompts.py         # MODIFY: Add Evidence field to OPTIONS template; citation instructions
│   │   │   └── orchestrator.py    # MODIFY: Expose structured context for snapshot capture
│   │   └── knowledge/
│   │       └── context_builder.py # READ ONLY: Provides structured context (no changes needed)
│   └── ...
└── tests/
    ├── unit/
    │   └── modules/
    │       └── insights/
    │           ├── test_evidence.py    # NEW: Evidence extraction unit tests
    │           └── test_thresholds.py  # NEW (P2): Threshold registry tests
    └── integration/
        └── api/
            └── test_insights_evidence.py  # NEW: Expand endpoint with evidence integration tests

frontend/
└── src/
    ├── types/
    │   └── insights.ts                    # MODIFY: Add data_snapshot to Insight interface
    ├── components/
    │   └── insights/
    │       ├── OptionsDisplay.tsx          # MODIFY: Add evidence section to OptionCard
    │       ├── InsightDetailPanel.tsx      # MODIFY: Hide confidence; add data freshness (P2)
    │       ├── EvidenceSection.tsx         # NEW: Collapsible evidence display component
    │       ├── DataFreshnessIndicator.tsx  # NEW (P2): "Data as of" badge component
    │       └── ThresholdTooltip.tsx        # NEW (P2): Threshold explanation tooltip
    └── ...
```

**Structure Decision**: Web application (Option 2). Changes span existing backend modules (`insights`, `agents`) and frontend components (`insights/`). Two new backend files (`evidence.py`, `thresholds.py`) and three new frontend components. No new modules or architectural changes.

## Complexity Tracking

No constitution violations. All changes fit within existing module boundaries and patterns.

| Aspect | Assessment |
|--------|-----------|
| New modules | 0 — all within existing `insights` and `agents` modules |
| New tables | 0 — uses existing `data_snapshot` JSONB column |
| New backend files | 2 (`evidence.py`, `thresholds.py`) |
| New frontend components | 3 (`EvidenceSection`, `DataFreshnessIndicator`, `ThresholdTooltip`) |
| Breaking API changes | 0 — all additive (new optional field) |
| Migration required | No — column already exists |

## Phase Breakdown

### Phase 1 (P1): Evidence + Snapshots + Hide Confidence
**Scope**: FR-001 to FR-011, FR-026a
**Backend**: `evidence.py` (new), `schemas.py`, `service.py`, `router.py`, `prompts.py`, `orchestrator.py`, `ai_analyzer.py`
**Frontend**: `EvidenceSection.tsx` (new), `OptionsDisplay.tsx`, `InsightDetailPanel.tsx`, `insights.ts`

Key implementation steps:
1. Create `evidence.py` — `build_evidence_snapshot()` function that extracts structured evidence from `ClientContext` and `perspective_contexts`, returns `DataSnapshot` Pydantic model bounded to 50KB
2. Add `**Evidence:**` field to `STRATEGY_OPTIONS_SYSTEM_PROMPT` in `prompts.py`
3. Modify `expand_insight()` in `router.py` — capture `client_context` and `multi_context` before prompt construction, call `build_evidence_snapshot()`, store in `insight.data_snapshot`
4. Update AI Analyzer to store real context (not stub) in `data_snapshot`
5. Add `data_snapshot` to `InsightResponse` schema and `_to_response()` method
6. Add `data_snapshot` to frontend `Insight` type
7. Create `EvidenceSection.tsx` — collapsible component using ExpandableSection pattern
8. Integrate `EvidenceSection` into `OptionsDisplay.tsx` OptionCard
9. Hide confidence score display in `InsightDetailPanel.tsx`

### Phase 2 (P2): Citations + Freshness + Thresholds
**Scope**: FR-012 to FR-023
**Backend**: `prompts.py`, `thresholds.py` (new), `router.py`
**Frontend**: `DataFreshnessIndicator.tsx` (new), `ThresholdTooltip.tsx` (new), various existing components

Key implementation steps:
1. Add citation instructions to Agent Orchestrator system prompt
2. Create `ThresholdRegistry` in `thresholds.py` with all platform threshold rules
3. Add `GET /api/v1/platform/thresholds` endpoint
4. Create `DataFreshnessIndicator` component — shows "Data as of [date]" + stale warning
5. Create `ThresholdTooltip` component — renders threshold rules from registry
6. Integrate freshness indicator into AI response rendering
7. Add threshold tooltips to quality scores, variance badges, risk labels, health indicators

### Phase 3 (P3): Confidence Reform + Export Safety + Mock Data
**Scope**: FR-024 to FR-030
**Backend**: Confidence calculation refactor, export enrichment
**Frontend**: Confidence breakdown display, export caveats, mock data watermark

Key implementation steps:
1. Replace hardcoded confidence with calculated score based on data completeness, freshness, knowledge match, perspective coverage
2. Create confidence breakdown display component
3. Enrich email/copy exports with disclaimers, freshness, confidence
4. Add "Sample Data" watermark to A2UI mock data fallbacks
