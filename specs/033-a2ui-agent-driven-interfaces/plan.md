# Implementation Plan: A2UI Agent-Driven Interfaces

**Branch**: `033-a2ui-agent-driven-interfaces` | **Date**: 2026-01-02 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/033-a2ui-agent-driven-interfaces/spec.md`

## Summary

Enable AI agents to generate dynamic, context-aware native UIs using Google's A2UI protocol. This transforms Clairo from static screens to intelligent interfaces that adapt based on user context, time of day, device type, and AI discoveries. The implementation adds an A2UI renderer and component catalog to the frontend, with minimal backend changes to add `/ui` endpoints that return A2UI JSON alongside existing data.

## Technical Context

**Language/Version**: TypeScript 5.x (frontend), Python 3.12 (backend)
**Primary Dependencies**:
- Frontend: React 18, Next.js 14, shadcn/ui, Recharts, TanStack Query
- Backend: FastAPI, Pydantic, LangGraph (existing AI agents)
**Storage**: N/A - A2UI is presentation layer only, no new tables
**Testing**: Vitest (frontend), pytest (backend)
**Target Platform**: Web (React), with mobile-responsive components
**Project Type**: Web application (frontend-heavy feature)
**Performance Goals**: <200ms A2UI render time, streaming UI support
**Constraints**: Must not break existing UIs, progressive enhancement only
**Scale/Scope**: 30+ component types, 6 user stories, additive API endpoints

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Monolith | PASS | A2UI adds new module `frontend/src/lib/a2ui/` with clear boundaries |
| Technology Stack | PASS | Uses existing React, TypeScript, shadcn/ui - no new frameworks |
| Repository Pattern | N/A | No database changes required |
| Multi-Tenancy | PASS | A2UI renders data already fetched with tenant context |
| Testing Strategy | PASS | Component tests for catalog, integration tests for renderer |
| Code Quality | PASS | TypeScript strict mode, Pydantic schemas for A2UI messages |
| API Design | PASS | Additive `/ui` endpoints follow REST conventions |
| Auditing | PASS | Action triggers logged, render failures logged |
| Human-in-the-Loop | PASS | A2UI presents AI suggestions, user confirms actions |

**Gate Result**: PASS - No violations requiring justification.

## Project Structure

### Documentation (this feature)

```text
specs/033-a2ui-agent-driven-interfaces/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output (A2UI schema types)
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output (OpenAPI for /ui endpoints)
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── lib/
│   │   └── a2ui/                    # A2UI Core Module
│   │       ├── index.ts             # Public exports
│   │       ├── types.ts             # A2UI message types
│   │       ├── renderer.tsx         # Main A2UI renderer component
│   │       ├── context.tsx          # Data model context provider
│   │       ├── catalog.ts           # Component registry
│   │       ├── streaming.ts         # Progressive rendering support
│   │       └── fallback.tsx         # Error fallback component
│   │
│   ├── components/
│   │   └── a2ui/                    # A2UI Component Implementations
│   │       ├── charts/              # Chart components
│   │       │   ├── LineChart.tsx
│   │       │   ├── BarChart.tsx
│   │       │   ├── PieChart.tsx
│   │       │   └── ScatterChart.tsx
│   │       ├── data/                # Data display components
│   │       │   ├── DataTable.tsx
│   │       │   ├── ComparisonTable.tsx
│   │       │   └── StatCard.tsx
│   │       ├── layout/              # Layout components
│   │       │   ├── Card.tsx
│   │       │   ├── Accordion.tsx
│   │       │   ├── Tabs.tsx
│   │       │   └── Timeline.tsx
│   │       ├── actions/             # Action components
│   │       │   ├── ActionButton.tsx
│   │       │   ├── ApprovalBar.tsx
│   │       │   └── ExportButton.tsx
│   │       ├── alerts/              # Alert components
│   │       │   ├── AlertCard.tsx
│   │       │   ├── UrgencyBanner.tsx
│   │       │   └── Badge.tsx
│   │       ├── forms/               # Form components
│   │       │   ├── TextInput.tsx
│   │       │   ├── SelectField.tsx
│   │       │   ├── Checkbox.tsx
│   │       │   ├── DateRangePicker.tsx
│   │       │   └── FilterBar.tsx
│   │       ├── media/               # Media components
│   │       │   ├── CameraCapture.tsx
│   │       │   ├── FileUpload.tsx
│   │       │   └── Avatar.tsx
│   │       └── feedback/            # Feedback components
│   │           ├── Progress.tsx
│   │           ├── Skeleton.tsx
│   │           ├── Tooltip.tsx
│   │           └── Dialog.tsx
│   │
│   ├── hooks/
│   │   ├── useA2UIRenderer.ts       # A2UI rendering hook
│   │   ├── useA2UIStream.ts         # Streaming A2UI hook
│   │   └── useDeviceContext.ts      # Device detection hook
│   │
│   └── app/
│       └── (protected)/
│           └── dashboard/
│               └── page.tsx          # Integrate A2UI dashboard

backend/
├── app/
│   ├── core/
│   │   └── a2ui/                    # A2UI Backend Module
│   │       ├── __init__.py
│   │       ├── schemas.py           # Pydantic A2UI schemas
│   │       ├── builder.py           # A2UI response builder
│   │       └── device.py            # Device context detection
│   │
│   └── modules/
│       ├── insights/
│       │   ├── router.py            # Add /insights/{id}/ui endpoint
│       │   └── a2ui_generator.py    # Insight-to-A2UI converter
│       │
│       ├── agents/
│       │   └── dashboard_agent.py   # Dashboard personalization agent
│       │
│       └── portal/
│           └── requests/
│               └── router.py        # Add /requests/{id}/ui endpoint
```

**Structure Decision**: Web application with frontend-heavy implementation. The A2UI renderer lives in frontend, with thin backend support for generating A2UI responses from existing services.

## Complexity Tracking

No violations to justify - all gates pass.
