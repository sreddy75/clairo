# Implementation Plan: BAS UX Polish & Xero Status Sync

**Branch**: `056-bas-ux-xero-status` | **Date**: 2026-04-10 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/056-bas-ux-xero-status/spec.md`

## Summary

Four changes to the BAS tax code resolution workflow: (1) remove the Reject action, keeping only Approve/Override/Park it, with a dedicated "Parked" section showing parked items with "Approve" and "Back to Manual" (unpark) actions, (2) add per-suggestion notes with inline editing, (3) optional fire-and-forget Xero sync of notes via History & Notes API (no persistent sync status tracking), (4) Xero BAS cross-check panel on tab load showing key figure comparison.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Anthropic SDK, React 18, shadcn/ui, TanStack Query
**Storage**: PostgreSQL 16 (3 new columns on `tax_code_suggestions`: `note_text`, `note_updated_by`, `note_updated_at` — no new tables)
**Testing**: pytest + pytest-asyncio (backend), TypeScript checks + ESLint (frontend)
**Target Platform**: Web application (Vercel frontend, AWS ECS backend)
**Project Type**: Web (modular monolith backend + Next.js frontend)
**Performance Goals**: Note save < 1s, Xero cross-check < 3s, no tab-load delay
**Constraints**: Xero rate limit 60/min per org, History & Notes `Details` max 450 chars, `GET /Reports/BAS` returns amounts only (no lodgement status)
**Scale/Scope**: ~50 tenants, ~500 BAS sessions/quarter, ~10k suggestions/quarter

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith architecture | ✅ Pass | All changes within `bas` module + `integrations/xero` module |
| Repository pattern | ✅ Pass | New repo methods for notes CRUD |
| Multi-tenancy (`tenant_id`) | ✅ Pass | New table includes `tenant_id` |
| Audit trail | ✅ Pass | Audit events defined for note CRUD and Xero sync |
| Domain exceptions (not HTTPException in services) | ✅ Pass | Service raises domain errors |
| Module boundary (no cross-module DB queries) | ✅ Pass | BAS module calls Xero service via public interface |
| Testing requirements | ✅ Pass | Unit + integration tests planned |
| API design (RESTful) | ✅ Pass | Standard CRUD endpoints for notes |

## Project Structure

### Documentation (this feature)

```text
specs/056-bas-ux-xero-status/
├── plan.md              # This file
├── spec.md              # Feature specification
├── research.md          # Phase 0 research
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Phase 1 quickstart
├── contracts/           # Phase 1 API contracts
│   ├── notes-api.md
│   ├── xero-crosscheck-api.md
│   └── reject-deprecation.md
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── bas/
│   │   │   ├── models.py              # Add note_text, note_updated_by, note_updated_at to TaxCodeSuggestion
│   │   │   ├── schemas.py             # Add note schemas, update suggestion response
│   │   │   ├── repository.py          # Add note CRUD methods
│   │   │   ├── tax_code_service.py    # Modify reject→dismiss ("Park it"), add note methods, add unpark
│   │   │   └── router.py             # Add note endpoints, unpark endpoint, deprecate reject
│   │   └── integrations/
│   │       └── xero/
│   │           ├── client.py          # Add get_bas_report(), add_history_note()
│   │           └── service.py         # Add BAS cross-check service method
│   └── alembic/
│       └── versions/                  # Migration for new columns
│
└── tests/
    ├── unit/modules/bas/
    │   └── test_tax_code_service.py   # Test reject→dismiss, note CRUD
    └── integration/api/
        └── test_bas_notes.py          # Integration tests for note endpoints

frontend/
└── src/
    ├── components/bas/
    │   ├── TaxCodeSuggestionCard.tsx   # Remove Reject button, add note icon
    │   ├── TaxCodeResolutionPanel.tsx  # Remove reject handler, add note handler
    │   ├── TransactionLineItemGroup.tsx # Remove reject prop
    │   ├── SuggestionNoteEditor.tsx    # NEW: inline note editor popover
    │   ├── XeroBASCrossCheck.tsx       # NEW: cross-check info panel
    │   └── BASTab.tsx                 # Add cross-check fetch on session detail load
    └── lib/
        └── bas.ts                     # Add note API functions, cross-check API, update types
```

**Structure Decision**: Web application structure following existing modular monolith. All backend changes in `bas` and `integrations/xero` modules. Frontend changes in `components/bas/` and `lib/bas.ts`.
