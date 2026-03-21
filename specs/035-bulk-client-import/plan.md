# Implementation Plan: Bulk Client Import via Multi-Org Xero OAuth

**Branch**: `035-bulk-client-import` | **Date**: 2026-02-08 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/035-bulk-client-import/spec.md`

## Summary

Enable accounting practices to connect multiple Xero client organizations in a single OAuth flow, replacing the current one-at-a-time approach. The implementation modifies the Xero OAuth callback to process all authorized organizations (not just the first), adds a post-authorization configuration screen, creates a batched background sync orchestrator with rate limit coordination, and provides a real-time progress dashboard. The existing `BulkImportJob` model is reused for tracking, and a new `BulkImportOrganization` table tracks per-org status within a job.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, Celery, Redis, Next.js 14, shadcn/ui, TanStack Query
**Storage**: PostgreSQL 16 (new table: `bulk_import_organizations`, new column on `xero_oauth_states`)
**Testing**: pytest with pytest-asyncio (backend), Playwright (E2E)
**Target Platform**: Web application (Docker-based backend, Vercel frontend)
**Project Type**: Web (backend + frontend)
**Performance Goals**: Configuration screen renders <2s with 25 orgs; progress dashboard polls every 2s; bulk import of 25 orgs completes OAuth+config in <5 min (excluding sync time)
**Constraints**: Max 25 concurrent Xero org connections (uncertified app); 10,000 API calls/min app-wide; 60 calls/min per-org; 5,000 calls/day per-org
**Scale/Scope**: 25 orgs per bulk import (uncertified); 10 concurrent syncs max; ~8 files backend, ~5 files frontend

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith (Section I) | PASS | All code within `modules/integrations/xero/` and `modules/onboarding/`. Cross-module access via service layer only. |
| Technology Stack (Section II) | PASS | Uses FastAPI, SQLAlchemy, Celery, Next.js, shadcn/ui — all approved stack. |
| Repository Pattern (Section III) | PASS | New `BulkImportOrganizationRepository` follows existing pattern. |
| Multi-Tenancy (Section IV) | PASS | `tenant_id` on `bulk_import_organizations`. RLS enforced. |
| Testing Strategy (Section V) | PASS | Unit tests for service logic, integration tests for all endpoints, contract tests for Xero API. |
| Code Quality (Section VI) | PASS | Type hints, Pydantic schemas, domain exceptions, HTTPException only in router. |
| API Design (Section VII) | PASS | RESTful endpoints under `/api/v1/integrations/xero/bulk-import/`. |
| External Integrations (Section VIII) | PASS | Extends existing Xero OAuth integration. Rate limit management enhanced. |
| Security (Section IX) | PASS | Encrypted tokens, Clerk auth, RLS. No new security concerns. |
| Auditing (Section X) | PASS | 6 audit events defined in spec. All financial data access logged. |
| Module Boundaries (Section I) | PASS | Xero bulk import stays in integrations/xero module. Uses onboarding model via import only. |

**Post-Phase 1 Re-check**: PASS — Data model adds one new table and one column, both tenant-scoped with RLS. No architectural violations.

## Project Structure

### Documentation (this feature)

```text
specs/035-bulk-client-import/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research findings
├── data-model.md        # Data model design
├── quickstart.md        # Developer quickstart guide
├── contracts/
│   └── api.yaml         # OpenAPI contract for bulk import endpoints
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Task list (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── integrations/xero/
│   │   │   ├── router.py            # New bulk import endpoints (6 endpoints)
│   │   │   ├── service.py           # BulkImportService class, handle_bulk_callback()
│   │   │   ├── schemas.py           # Bulk import request/response Pydantic schemas
│   │   │   └── models.py            # XeroOAuthState.is_bulk_import column
│   │   └── onboarding/
│   │       ├── models.py            # BulkImportOrganization model (new table)
│   │       └── repository.py        # BulkImportOrganizationRepository
│   ├── tasks/
│   │   └── xero.py                  # run_bulk_xero_import Celery task
│   └── alembic/versions/
│       └── xxx_add_bulk_import_organizations.py
└── tests/
    ├── unit/modules/integrations/xero/
    │   └── test_bulk_import_service.py
    ├── integration/api/
    │   └── test_bulk_import.py
    └── contract/adapters/
        └── test_xero_bulk_connections.py

frontend/
├── src/
│   ├── app/(protected)/clients/
│   │   ├── page.tsx                 # Add "Import Clients from Xero" button
│   │   └── import/
│   │       ├── page.tsx             # Post-OAuth configuration screen
│   │       └── progress/
│   │           └── [jobId]/
│   │               └── page.tsx     # Real-time progress dashboard
│   ├── lib/api/
│   │   └── bulk-import.ts           # Typed API client functions
│   └── types/
│       └── bulk-import.ts           # TypeScript interfaces
```

**Structure Decision**: Web application structure following the existing Clairo modular monolith pattern. Backend code primarily in `modules/integrations/xero/` with the `BulkImportOrganization` model co-located in `modules/onboarding/` alongside the existing `BulkImportJob` model. Frontend adds new pages under the clients route.

## Complexity Tracking

No constitution violations. No complexity justifications needed.
