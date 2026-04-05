# Quickstart: Onboarding & Core Hardening

**Branch**: `054-onboarding-hardening` | **Date**: 2026-04-05

## Prerequisites

- Docker Compose running (PostgreSQL, Redis, MinIO)
- Backend: `cd backend && uv sync`
- Frontend: `cd frontend && npm install`
- Xero sandbox credentials (optional — tests can use mocked data)

## What Changes

### Backend

```
backend/
├── alembic/versions/
│   └── xxx_add_rls_policies_missing_tables.py  # NEW: RLS for 16 tables
└── tests/
    ├── integration/
    │   ├── test_rls_policies.py                # MODIFIED: +16 table tests
    │   └── api/
    │       ├── test_tenant_isolation.py         # REWRITTEN: replace placeholder
    │       ├── test_bas_workflow.py             # MODIFIED: +full lifecycle tests
    │       └── test_tax_planning_workflow.py    # NEW: plan lifecycle tests
    └── factories/
        ├── bas.py                              # NEW: BAS session/suggestion factories
        └── tax_planning.py                     # NEW: tax plan/scenario factories
```

### Frontend

```
frontend/src/
├── app/
│   └── portal/
│       ├── dashboard/page.tsx                  # MODIFIED: add empty state for no data
│       └── tax-plan/page.tsx                   # MODIFIED: improve no-plan state
├── components/
│   └── tax-planning/
│       └── TaxPlanningWorkspace.tsx            # MODIFIED: improve empty state messaging
```

## Database Migration

```bash
cd backend && uv run alembic revision -m "Add RLS policies to 16 tenant-scoped tables"
cd backend && uv run alembic upgrade head
```

Adds RLS policies to: portal_invitations, portal_sessions, document_request_templates, bulk_requests, document_requests, portal_documents, tax_code_suggestions, tax_code_overrides, classification_requests, client_classifications, feedback_submissions, tax_plans, tax_scenarios, tax_plan_messages, tax_plan_analyses, implementation_items.

## Running Tests

```bash
# All integration tests
cd backend && uv run pytest tests/integration/ -v

# RLS policy tests only
cd backend && uv run pytest tests/integration/test_rls_policies.py -v

# Tenant isolation API tests only
cd backend && uv run pytest tests/integration/api/test_tenant_isolation.py -v

# BAS workflow tests only
cd backend && uv run pytest tests/integration/api/test_bas_workflow.py -v

# Tax planning workflow tests only
cd backend && uv run pytest tests/integration/api/test_tax_planning_workflow.py -v
```

## Validation

```bash
# Full backend validation
cd backend && uv run ruff check . && uv run pytest

# Frontend
cd frontend && npm run lint && npx tsc --noEmit

# Verify RLS policies are active (psql)
SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename;
```
