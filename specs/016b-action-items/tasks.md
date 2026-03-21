# Tasks: Action Items (Spec 016b)

**Input**: Design documents from `/specs/016b-action-items/`
**Prerequisites**: plan.md (required), spec.md (required)
**Branch**: `feature/016b-action-items`

---

## Implementation Status

| Phase | Status | Tasks |
|-------|--------|-------|
| Phase 0: Git Setup | ✅ Complete | T000 |
| Phase 1: Backend Model | ✅ Complete | T001-T004 |
| Phase 2: API Endpoints | ✅ Complete | T005-T008 |
| Phase 3: Frontend Page | ✅ Complete | T009-T013 |
| Phase 4: Integration | ✅ Complete | T014-T017 |
| Phase 5: Polish | ✅ Complete | T018-T020 |
| Phase FINAL: PR & Merge | ✅ Complete | TFINAL |

**Last Updated**: 2025-12-31
**Status**: COMPLETE

---

## Format: `[ID] [P?] Description`

- **[P]**: Can run in parallel (different files, no dependencies)

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [x] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/016b-action-items`
  - Verify: You are now on the feature branch

---

## Phase 1: Backend Model

**Purpose**: Database model and service layer

- [x] T001 Create action_items module structure
  - Create: `backend/app/modules/action_items/__init__.py`
  - Create: `backend/app/modules/action_items/models.py`
  - Create: `backend/app/modules/action_items/schemas.py`
  - Create: `backend/app/modules/action_items/service.py`
  - Create: `backend/app/modules/action_items/router.py`

- [x] T002 Create database migration
  - Create: `backend/alembic/versions/019_action_items.py`
  - Table: `action_items` with all fields from plan.md
  - Indexes: tenant_id, status, assigned_to_user_id, due_date, client_id
  - FK: source_insight_id → insights(id) ON DELETE SET NULL
  - FK: client_id → xero_connections(id) ON DELETE SET NULL
  - RLS: Enable row level security
  - Additional: `backend/alembic/versions/020_action_items_notes.py` for notes field

- [x] T003 Implement ActionItem model and enums
  - File: `backend/app/modules/action_items/models.py`
  - Enums: `ActionItemStatus` (pending, in_progress, completed, cancelled)
  - Enums: `ActionItemPriority` (urgent, high, medium, low)
  - Model: `ActionItem` SQLAlchemy model with all fields
  - Relationships: insight (optional), xero_connection (optional)
  - Added: `notes` field for internal notes

- [x] T004 Implement schemas
  - File: `backend/app/modules/action_items/schemas.py`
  - `ActionItemCreate` - title, description, notes, client_id, due_date, priority, assigned_to_user_id, source_insight_id
  - `ActionItemUpdate` - all optional fields
  - `ActionItemResponse` - full response with computed fields
  - `ActionItemListResponse` - paginated list
  - `ActionItemStats` - counts by status for dashboard
  - `ConvertInsightRequest` - for converting insights to action items

**Checkpoint**: ✅ Model and schemas defined, migration ready

---

## Phase 2: API Endpoints

**Purpose**: REST API for action items

- [x] T005 Implement ActionItemService
  - File: `backend/app/modules/action_items/service.py`
  - `create()` - create action item, denormalize client_name/assigned_name
  - `get_by_id()` - get single item
  - `list()` - list with filters (status, priority, assignee, client, due_date range)
  - `update()` - update fields
  - `delete()` - hard delete
  - `start()` - set status=in_progress, started_at=now
  - `complete()` - set status=completed, completed_at=now
  - `cancel()` - set status=cancelled
  - `get_stats()` - counts for dashboard widget

- [x] T006 Implement router endpoints
  - File: `backend/app/modules/action_items/router.py`
  - `POST /api/v1/action-items` - create
  - `GET /api/v1/action-items` - list with query params
  - `GET /api/v1/action-items/:id` - get one
  - `GET /api/v1/action-items/stats` - get stats
  - `PATCH /api/v1/action-items/:id` - update
  - `DELETE /api/v1/action-items/:id` - delete
  - `POST /api/v1/action-items/:id/start` - mark in progress
  - `POST /api/v1/action-items/:id/complete` - mark completed
  - `POST /api/v1/action-items/:id/cancel` - mark cancelled

- [x] T007 Add convert insight endpoint
  - File: `backend/app/modules/insights/router.py`
  - `POST /api/v1/insights/:id/convert-to-action` - create action from insight
  - Pre-fill: title, client_id, priority mapping
  - Update insight status to ACTIONED
  - Fixed: client_name access via relationship

- [x] T008 Register router in main app
  - File: `backend/app/main.py`
  - Add: `from app.modules.action_items.router import router as action_items_router`
  - Add: `app.include_router(action_items_router)`

**Checkpoint**: ✅ API endpoints working

---

## Phase 3: Frontend Page

**Purpose**: Action Items list page

- [x] T009 [P] Create TypeScript types
  - Create: `frontend/src/types/action-items.ts`
  - Types: `ActionItem`, `ActionItemStatus`, `ActionItemPriority`
  - Types: `ActionItemCreate`, `ActionItemUpdate`, `ActionItemStats`
  - Added: `notes` field, `PRIORITY_CONFIG` for display

- [x] T010 [P] Create API client
  - Create: `frontend/src/lib/api/action-items.ts`
  - Functions: `listActionItems()`, `getActionItem()`, `createActionItem()`
  - Functions: `updateActionItem()`, `deleteActionItem()`
  - Functions: `startActionItem()`, `completeActionItem()`, `cancelActionItem()`
  - Functions: `getActionItemStats()`, `convertInsightToAction()`

- [x] T011 Create ActionItemCard component
  - Create: `frontend/src/components/action-items/ActionItemCard.tsx`
  - Display: title, priority badge, client name, due date, assignee
  - Overdue highlighting (red if past due)
  - Source insight link (if from insight)
  - Actions: Start, Complete, Cancel, Delete

- [x] T012 Create ActionItemFilters component
  - Create: `frontend/src/components/action-items/ActionItemFilters.tsx`
  - Quick filter tabs: All, Urgent, Overdue, Mine
  - Dropdowns: Status, Priority
  - Include completed toggle

- [x] T013 Create Action Items page
  - Create: `frontend/src/app/(protected)/action-items/page.tsx`
  - Layout: Header with "+ New Action Item" button
  - Stats summary cards
  - Quick filter tabs
  - Detailed filters bar
  - Action items list with cards
  - Pagination
  - Empty state when no items
  - Loading state
  - Error handling with retry

**Checkpoint**: ✅ Action Items page renders with real data

---

## Phase 4: Integration

**Purpose**: Connect insights to actions, add widget

- [x] T014 Create CreateActionModal component
  - Create: `frontend/src/components/action-items/CreateActionItemModal.tsx`
  - Form: title, description, due_date, priority, assignee, notes
  - Assignee dropdown from tenant users (via `/api/v1/auth/users`)
  - Shows "(Me)" next to current user

- [x] T015 Add "Convert to Action" on insight cards
  - Create: `frontend/src/components/action-items/ConvertInsightModal.tsx`
  - Pre-fill from insight data
  - Assignee dropdown from tenant users
  - Notes field for internal notes
  - Refresh insights after conversion

- [x] T016 Create users API client
  - Create: `frontend/src/lib/api/users.ts`
  - `listTenantUsers()` - fetch users for assignee dropdown

- [x] T017 Export all components
  - Create: `frontend/src/components/action-items/index.ts`
  - Exports: ActionItemCard, ActionItemFiltersBar, QuickFilterTabs
  - Exports: ConvertInsightModal, CreateActionItemModal
  - Exports: ActionItemFilters type

**Checkpoint**: ✅ Full flow works - insight → action → complete

---

## Phase 5: Polish

**Purpose**: Navigation, edge cases, UX refinements

- [x] T018 Add navigation link
  - Update: `frontend/src/app/(protected)/layout.tsx`
  - Add: "Action Items" nav entry with ListTodo icon
  - Position in sidebar navigation

- [x] T019 Handle edge cases
  - Empty states with helpful messages
  - Error handling for API failures with retry
  - Confirm dialog for delete
  - Form validation

- [x] T020 Run lint and fix issues
  - Backend: Fixed router imports (`get_current_tenant_id`, `get_db`)
  - Frontend: Components properly typed

**Checkpoint**: ✅ Polish complete

---

## Phase FINAL: PR & Merge (REQUIRED)

- [x] TFINAL-1 Run all tests and linting
  - Backend: Verified working
  - Frontend: Verified working

- [x] TFINAL-2 Commit all changes
  - Multiple commits for feature implementation

- [x] TFINAL-3 Merge to main
  - Feature merged to main

- [x] TFINAL-4 Push to remote
  - Pushed to origin/main

- [x] TFINAL-5 Update ROADMAP.md
  - Mark Spec 016b as COMPLETE

---

## Dependencies

```
Phase 0 (Git) → Phase 1 (Model) → Phase 2 (API) → Phase 3 (Frontend)
                                                         ↓
                                              Phase 4 (Integration)
                                                         ↓
                                              Phase 5 (Polish)
                                                         ↓
                                              Phase FINAL (Merge)
```

---

## Notes

- Keep scope minimal - no notifications, recurring tasks, etc.
- Team assignment is simple dropdown (no complex permissions)
- Default filter excludes completed items
- Hard delete implemented (not soft delete)
- Notes field added for internal tracking
- Users API created for assignee dropdown
