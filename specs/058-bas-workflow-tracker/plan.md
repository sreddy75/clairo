# Implementation Plan: BAS Workflow Tracker — Practice Management Layer

**Branch**: `058-bas-workflow-tracker` | **Date**: 2026-04-15 | **Spec**: [spec.md](spec.md)  
**Input**: Feature specification from `/specs/058-bas-workflow-tracker/spec.md`

## Summary

Add a practice management layer to the BAS workflow: team assignment (persistent per-client), per-quarter client exclusion, persistent client notes, non-Xero client visibility, and smarter readiness signals incorporating reconciliation status. The core technical approach is a new `PracticeClient` entity that wraps both Xero-connected and manually-added clients into a unified dashboard, with the dashboard query refactored to drive from this entity.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)  
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Alembic, React 18 + shadcn/ui, Clerk  
**Storage**: PostgreSQL 16 (3 new tables: `practice_clients`, `client_quarter_exclusions`, `client_note_history`; 1 modified: `practice_users`)  
**Testing**: pytest + pytest-asyncio (backend), TypeScript compiler (frontend)  
**Target Platform**: Web (desktop + responsive)  
**Project Type**: Web (modular monolith backend + Next.js frontend)  
**Performance Goals**: Dashboard loads <2s for 280 clients; team filter/exclusion toggle <500ms  
**Constraints**: Multi-tenancy via tenant_id + RLS; audit logging for all data modifications  
**Scale/Scope**: Practices with 100-300 clients, 2-5 team members

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith boundaries | PASS | New models in clients module, dashboard module updated for queries. No cross-module DB queries — dashboard calls clients service for practice_client data |
| Repository pattern | PASS | All DB access via ClientsRepository and DashboardRepository |
| Multi-tenancy | PASS | All new tables have tenant_id + RLS policies |
| Audit-first | PASS | 6 audit event types defined; client_note_history is append-only |
| Domain exceptions | PASS | Service raises domain exceptions; router converts to HTTPException |
| No cross-module imports | PASS | Dashboard imports ClientsService, not clients models directly |
| flush() not commit() | PASS | Repository methods use flush(); session lifecycle managed by caller |

**Post-Phase 1 re-check**: All gates remain PASS. The `PracticeClient` entity cleanly separates practice management from Xero integration. The dashboard refactor queries through `practice_clients` with optional joins to `xero_connections` — no direct cross-module table access.

## Project Structure

### Documentation (this feature)

```text
specs/058-bas-workflow-tracker/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research decisions
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 implementation guide
├── contracts/
│   └── api.md           # API contracts
└── checklists/
    └── requirements.md  # Spec quality checklist
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── clients/
│   │   │   ├── models.py          # +PracticeClient, ClientQuarterExclusion, ClientNoteHistory
│   │   │   ├── repository.py      # +CRUD for new entities
│   │   │   ├── service.py         # +assignment, exclusion, notes logic
│   │   │   ├── schemas.py         # +new Pydantic schemas
│   │   │   └── router.py          # +new endpoints
│   │   ├── dashboard/
│   │   │   ├── repository.py      # Refactored: query from practice_clients
│   │   │   ├── service.py         # Extended: new filter params
│   │   │   └── schemas.py         # Extended: new response fields
│   │   ├── auth/
│   │   │   ├── models.py          # +display_name on PracticeUser
│   │   │   └── schemas.py         # +display_name on PracticeUserResponse
│   │   └── integrations/xero/
│   │       └── bulk_import_service.py  # +create PracticeClient during import
│   └── alembic/versions/
│       └── xxxx_add_practice_clients.py  # Migration
└── tests/
    ├── unit/modules/clients/
    │   └── test_practice_client_service.py
    └── integration/api/
        └── test_practice_clients.py

frontend/
└── src/
    ├── app/(protected)/
    │   ├── dashboard/page.tsx     # +team filter, new columns, exclusion UI, bulk assign, add client
    │   └── clients/[id]/page.tsx  # +notes editor section
    ├── components/
    │   ├── bas/BASTab.tsx         # +persistent notes banner
    │   ├── dashboard/             # New: extracted components for team filter, exclusion modal
    │   └── clients/               # New: manual client form, notes editor
    └── lib/
        └── constants/status.ts    # +accounting software indicators
```

**Structure Decision**: Extends the existing `clients` and `dashboard` modules. No new module needed — follows the modular monolith pattern of extending existing modules for related concerns.

## Complexity Tracking

No constitution violations. All design decisions align with existing patterns.
