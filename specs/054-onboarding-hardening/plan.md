# Implementation Plan: Onboarding & Core Hardening

**Branch**: `054-onboarding-hardening` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/054-onboarding-hardening/spec.md`

## Summary

Harden Clairo for beta launch by closing multi-tenancy security gaps (16 tables missing RLS), verifying BAS and tax planning workflows end-to-end with integration tests, improving empty states for new users, and verifying portal and RAG flows. This is a hardening spec — most code exists, the work is verification, gap-filling, and test writing.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, pytest + pytest-asyncio, factory_boy
**Storage**: PostgreSQL 16 (16 new RLS policies, no schema changes)
**Testing**: pytest + pytest-asyncio (backend), ESLint + tsc (frontend)
**Target Platform**: Web — accountant SaaS platform
**Project Type**: Web (backend + frontend)
**Performance Goals**: Tests complete within CI timeout. Empty states render instantly.
**Constraints**: Xero sandbox credentials may not be available — BAS tests must work with mocked data. No new tables or columns.
**Scale/Scope**: ~10 tenants at beta, ~50 users. Test suite covers all tenant-scoped tables.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | No new modules. Tests added to existing test directories. |
| Repository pattern | PASS | Verifying existing repository queries include tenant_id. |
| Multi-tenancy | PASS | This spec *is* the multi-tenancy hardening story — adds 16 missing RLS policies. |
| Tech stack compliance | PASS | Python 3.12, pytest, factory_boy — all existing dependencies. |
| Audit events | PASS | No new audit events. Existing audit coverage verified by tests. |
| Testing strategy | PASS | Integration tests for BAS, tax planning, portal, RLS, tenant isolation. |
| API design standards | PASS | No new endpoints. Verifying existing endpoints work correctly. |
| Human-in-the-loop | PASS | No changes to AI flows — verifying they work correctly. |
| No financial advice | PASS | AI disclaimer already implemented (spec 052). |

## Project Structure

### Documentation (this feature)

```text
specs/054-onboarding-hardening/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # RLS policy additions (no new tables)
├── quickstart.md        # Developer quickstart
├── contracts/
│   └── api.md           # Endpoints under test (no new endpoints)
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── alembic/versions/
│   └── xxx_add_rls_policies_missing_tables.py  # RLS migration
└── tests/
    ├── integration/
    │   ├── test_rls_policies.py                # +16 table tests
    │   └── api/
    │       ├── test_tenant_isolation.py         # Replace placeholder
    │       ├── test_bas_workflow.py             # +lifecycle tests
    │       └── test_tax_planning_workflow.py    # New
    └── factories/
        ├── bas.py                              # New
        └── tax_planning.py                     # New

frontend/src/
├── app/portal/
│   ├── dashboard/page.tsx                      # +empty state
│   └── tax-plan/page.tsx                       # +no-plan state
```

**Structure Decision**: No new modules or directories beyond test files and one migration. Frontend changes are minimal empty state improvements.

## Key Reuse Opportunities

| Existing Component | Reuse For | Location |
|---|---|---|
| RLS Pattern B SQL | Template for all 16 policies | `alembic/versions/006_bas_workflow.py:275-310` |
| `set_tenant_context()` helper | RLS test setup | `tests/integration/test_rls_policies.py:156-163` |
| `TenantFactory` / `create_tenant_with_admin()` | All isolation tests | `tests/factories/auth.py` |
| Portal factories | Portal flow tests | `tests/factories/portal.py` |
| Xero factories | BAS workflow tests | `tests/factories/xero.py` |
| Dashboard empty state pattern | Portal empty state | `dashboard/page.tsx:617-628` |

## Implementation Phases

### Phase 1: RLS Policies (US4 — highest security priority)
- Alembic migration adding RLS to 16 tables
- Special case: `document_request_templates` needs dual policy (tenant + system templates)
- Extend `test_rls_policies.py` with tests for all 16 tables
- Verify with `SELECT * FROM pg_policies`

### Phase 2: Empty States & Portal Polish (US1)
- Fix portal dashboard empty state (no shared data case)
- Fix portal tax plan page (friendly message instead of 404)
- Audit all major screens for empty state quality
- Verify portal invite flow end-to-end

### Phase 3: Tenant Isolation Tests (US4 continued)
- Replace `test_tenant_isolation.py` placeholder with real API-level tests
- Test cross-tenant isolation for: clients, BAS, tax plans, insights, portal
- Create test factories for BAS and tax planning data

### Phase 4: BAS Workflow Tests (US2)
- Create BAS test factories
- Write integration tests: session creation → suggestions → approval → calculation → export
- Verify GST calculation accuracy
- Verify export format (PDF working paper, ATO CSV)

### Phase 5: Tax Planning Workflow Tests (US3)
- Create tax planning test factories
- Write integration tests: plan creation → AI chat (mocked) → analysis → PDF export
- Test all entity types (individual, company, trust)
- Verify PDF includes disclaimer

### Phase 6: Knowledge/RAG Verification (US5)
- Manual verification checklist for RAG citation accuracy
- Verify citation sources exist in knowledge base
- Document any citation quality issues for follow-up

## Complexity Tracking

No constitution violations. All work extends existing infrastructure (test framework, RLS patterns, empty state components). The 16-table RLS migration is the highest-impact change — it's a security fix, not new complexity.
