# Quickstart: 058-bas-workflow-tracker

**Branch**: `058-bas-workflow-tracker`  
**Date**: 2026-04-15

---

## Prerequisites

- Python 3.12+, Node.js 18+, Docker running
- `docker-compose up -d` (PostgreSQL, Redis)
- Backend: `cd backend && uv sync`
- Frontend: `cd frontend && npm install`

---

## Implementation Order

### Phase 1: Data Foundation (backend only)

1. **New models** in `backend/app/modules/clients/models.py`:
   - `PracticeClient` — universal client entity
   - `ClientQuarterExclusion` — per-quarter exclusion
   - `ClientNoteHistory` — note audit trail

2. **Alembic migration**:
   - Create 3 new tables + add `display_name` to `practice_users`
   - Backfill `practice_clients` from existing `xero_connections`
   - Backfill `assigned_user_id` from `bulk_import_organizations`

3. **Verify**: `cd backend && uv run alembic upgrade head && uv run pytest`

### Phase 2: Backend API (team assignment + exclusion)

4. **Extend clients module**:
   - `clients/repository.py` — CRUD for PracticeClient, ClientQuarterExclusion
   - `clients/service.py` — assignment, exclusion, notes business logic
   - `clients/schemas.py` — Pydantic schemas for new endpoints
   - `clients/router.py` — new endpoints (POST /manual, PATCH /assign, POST /bulk-assign, etc.)

5. **Refactor dashboard module**:
   - `dashboard/repository.py` — rewrite `list_connections_with_financials` to query from `practice_clients`
   - `dashboard/schemas.py` — add new fields to `ClientPortfolioItem`, `DashboardSummaryResponse`
   - `dashboard/service.py` — pass through new filter params

6. **Verify**: `uv run pytest` — all existing + new tests pass

### Phase 3: Readiness signal enhancement (backend)

7. **Add unreconciled count** to dashboard query (subquery on `xero_bank_transactions`)
8. **Update BAS status derivation** — add reconciliation check to Python logic
9. **Verify**: test that high unreconciled count → NEEDS_REVIEW

### Phase 4: Frontend — dashboard enhancements

10. **Team member filter** — add "My Clients" / team member dropdown above filter tabs
11. **New columns** — assigned_user_name, unreconciled_count, accounting_software indicator
12. **Exclusion UI** — exclude button per row, "Excluded" filter tab, reverse action
13. **Bulk assignment** — row selection checkboxes + bulk assign dropdown
14. **Manual client creation** — "Add Client" button + form dialog

### Phase 5: Frontend — notes + BAS session integration

15. **Notes editor** on client detail page
16. **Notes banner** in BASTab — show persistent notes above session content
17. **Note history** — expandable history panel

### Phase 6: Import flow fix

18. **Propagate assigned_user_id** from `BulkImportOrganization` → `PracticeClient` during import completion

---

## Key Files to Modify

### Backend

| File | Changes |
|------|---------|
| `backend/app/modules/clients/models.py` | Add PracticeClient, ClientQuarterExclusion, ClientNoteHistory models |
| `backend/app/modules/clients/repository.py` | CRUD for new entities |
| `backend/app/modules/clients/service.py` | Business logic for assignment, exclusion, notes |
| `backend/app/modules/clients/schemas.py` | New Pydantic schemas |
| `backend/app/modules/clients/router.py` | New endpoints |
| `backend/app/modules/dashboard/repository.py` | Refactor main query to use practice_clients |
| `backend/app/modules/dashboard/service.py` | Pass new filters, compose extended response |
| `backend/app/modules/dashboard/schemas.py` | Extend ClientPortfolioItem, DashboardSummaryResponse |
| `backend/app/modules/auth/models.py` | Add display_name to PracticeUser |
| `backend/app/modules/auth/schemas.py` | Add display_name to PracticeUserResponse |
| `backend/app/modules/integrations/xero/bulk_import_service.py` | Create PracticeClient during import |

### Frontend

| File | Changes |
|------|---------|
| `frontend/src/app/(protected)/dashboard/page.tsx` | Team filter, new columns, exclusion UI, bulk assignment, "Add Client" button |
| `frontend/src/components/bas/BASTab.tsx` | Persistent notes banner above session content |
| `frontend/src/app/(protected)/clients/[id]/page.tsx` | Notes editor section on client detail |
| `frontend/src/lib/constants/status.ts` | Add accounting_software icons/labels |

### Tests

| File | Coverage |
|------|----------|
| `backend/tests/unit/modules/clients/test_practice_client_service.py` | Assignment, exclusion, notes CRUD |
| `backend/tests/integration/api/test_practice_clients.py` | New endpoint integration tests |
| `backend/tests/unit/modules/dashboard/test_dashboard_repository.py` | Refactored query with new filters |

---

## Validation Commands

```sh
# Backend
cd backend && uv run alembic upgrade head
cd backend && uv run pytest -x
cd backend && uv run ruff check .

# Frontend
cd frontend && npm run lint
cd frontend && npx tsc --noEmit
cd frontend && npm run dev  # manual test

# Full
cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit
```
