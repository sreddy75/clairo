# Tasks: Admin Dashboard (Internal)

**Input**: Design documents from `/specs/022-admin-dashboard/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/openapi.yaml

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [X] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/022-admin-dashboard`
  - Verify: You are now on the feature branch
  - _Note: Branch already exists - skip if already on feature branch_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Create new files and schemas needed by multiple user stories

- [X] T001 [P] Create admin domain exceptions in backend/app/modules/admin/exceptions.py
  - `TenantNotFoundError`, `TierChangeError`, `CreditApplicationError`, `FeatureFlagOverrideError`
  - All inherit from base `AdminError`
  - No HTTPException - domain exceptions only

- [X] T002 [P] Create FeatureFlagOverride model in backend/app/modules/admin/models.py
  - SQLAlchemy model per data-model.md
  - Fields: id, tenant_id, feature_key, override_value, reason, created_by, updated_by, timestamps
  - Add indexes and constraints

- [X] T003 Create Alembic migration for feature_flag_overrides table
  - Run: `uv run alembic revision --autogenerate -m "Add feature_flag_overrides table"`
  - Verify migration includes indexes and constraints

- [X] T004 [P] Extend admin schemas in backend/app/modules/admin/schemas.py
  - Add all Pydantic schemas from contracts/openapi.yaml
  - TenantSummary, TenantListResponse, TenantDetailResponse
  - RevenueMetricsResponse, RevenueTrendsResponse
  - TierChangeRequest/Response, CreditRequest/Response
  - FeatureFlagsResponse, FeatureFlagOverrideRequest/Response

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Repository and service infrastructure that all user stories depend on

**CRITICAL**: No user story work can begin until this phase is complete

- [X] T005 Create AdminRepository in backend/app/modules/admin/repository.py
  - `list_tenants(filters, pagination)` - paginated tenant query
  - `get_tenant(tenant_id)` - single tenant with relationships
  - `update_tenant_tier(tenant_id, new_tier)` - tier update
  - `create_billing_event(event_data)` - audit logging

- [X] T006 Create FeatureFlagOverrideRepository in backend/app/modules/admin/repository.py
  - `get_by_tenant(tenant_id)` - all overrides for tenant
  - `get_override(tenant_id, feature_key)` - single override
  - `upsert_override(tenant_id, feature_key, value, reason, admin_id)`
  - `delete_override(tenant_id, feature_key)`

- [X] T007 Create AdminDashboardService in backend/app/modules/admin/service.py
  - Initialize with session, stripe_client
  - Wire up AdminRepository and FeatureFlagOverrideRepository
  - Add structlog logging for all operations

- [X] T008 [P] Create admin API client in frontend/src/lib/api/admin.ts
  - TypeScript types matching backend schemas
  - `listTenants`, `getTenant`, `getRevenueMetrics`, `getRevenueTrends`
  - `changeTenantTier`, `applyCredit`
  - `getTenantFeatureFlags`, `setFeatureFlagOverride`, `deleteFeatureFlagOverride`

- [X] T009 [P] Create useAdminDashboard hook in frontend/src/hooks/useAdminDashboard.ts
  - TanStack Query hooks for all admin API calls
  - `useTenants`, `useTenant`, `useRevenueMetrics`
  - Mutation hooks for tier change, credits, feature flags

- [X] T010 Create admin layout in frontend/src/app/(protected)/internal/admin/layout.tsx
  - Admin-only middleware check
  - Sidebar navigation (Dashboard, Customers, Revenue)
  - Header with admin indicator

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - View All Customers (Priority: P1) - MVP

**Goal**: Operators can see all tenants in a searchable, sortable, paginated list

**Independent Test**: Load /internal/admin/customers and verify tenant list displays with search/filter/sort working

### Implementation for User Story 1

- [X] T011 [US1] Add list_tenants service method in backend/app/modules/admin/service.py
  - Accept filters: search, tier, status
  - Accept pagination: page, limit
  - Accept sorting: sort_by (name, created_at, mrr, client_count), sort_order
  - Return paginated TenantListResponse

- [X] T012 [US1] Add GET /admin/tenants endpoint in backend/app/modules/admin/router.py
  - Query params per contracts/openapi.yaml
  - Use require_admin() dependency
  - Return TenantListResponse schema

- [X] T013 [P] [US1] Create TenantTable component in frontend/src/app/(protected)/internal/admin/components/TenantTable.tsx
  - Table with columns: name, email, tier, clients, MRR, status, created
  - Search input (debounced)
  - Tier and status filter dropdowns
  - Column sorting (clickable headers)
  - Pagination controls

- [X] T014 [US1] Create customers list page in frontend/src/app/(protected)/internal/admin/customers/page.tsx
  - Use useTenants hook
  - Render TenantTable with loading/error states
  - Link rows to tenant detail page

- [X] T015 [US1] Create admin dashboard overview in frontend/src/app/(protected)/internal/admin/page.tsx
  - Quick stats cards (total tenants, active, by tier)
  - Link to customers page
  - Placeholder for revenue metrics (US2)

**Checkpoint**: User Story 1 complete - tenant list is functional and testable

---

## Phase 4: User Story 2 - Monitor Revenue Metrics (Priority: P1)

**Goal**: Operators can view MRR, churn, and expansion metrics with trends

**Independent Test**: Load /internal/admin/revenue and verify metrics display with correct calculations

### Implementation for User Story 2

- [X] T016 [US2] Add RevenueService in backend/app/modules/admin/service.py
  - `get_revenue_metrics(start_date, end_date)` - MRR, churn, expansion
  - `get_revenue_trends(period, months)` - historical trend data
  - Use Stripe API to fetch subscription data
  - Cache results in Redis (5-minute TTL)

- [X] T017 [US2] Add revenue endpoints in backend/app/modules/admin/router.py
  - GET /admin/revenue/metrics per contracts/openapi.yaml
  - GET /admin/revenue/trends per contracts/openapi.yaml
  - Both require admin auth

- [X] T018 [P] [US2] Create RevenueMetrics component in frontend/src/app/(protected)/internal/admin/components/RevenueMetrics.tsx
  - MRR card with current value and trend indicator
  - Churn rate card with percentage and lost amount
  - Expansion revenue card with upgrade/downgrade counts
  - Date range selector

- [X] T019 [P] [US2] Create RevenueTrendsChart component in frontend/src/app/(protected)/internal/admin/components/RevenueTrendsChart.tsx
  - Line chart showing MRR over time
  - Period selector (daily, weekly, monthly)
  - Use recharts library

- [X] T020 [US2] Create revenue page in frontend/src/app/(protected)/internal/admin/revenue/page.tsx
  - Use useRevenueMetrics and useRevenueTrends hooks
  - Render RevenueMetrics and RevenueTrendsChart
  - Handle loading and error states

- [X] T021 [US2] Update admin dashboard overview to include revenue summary
  - Add MRR summary card to frontend/src/app/(protected)/internal/admin/page.tsx
  - Link to full revenue page

**Checkpoint**: User Stories 1 AND 2 complete - both independently testable

---

## Phase 5: User Story 3 - View Tenant Details (Priority: P2)

**Goal**: Operators can view comprehensive tenant information including billing, usage, and history

**Independent Test**: Click any tenant from list and verify all detail sections display correctly

### Implementation for User Story 3

- [X] T022 [US3] Add get_tenant_detail service method in backend/app/modules/admin/service.py
  - Fetch tenant with relationships (billing events, users)
  - Merge feature flags (tier defaults + overrides)
  - Calculate MRR contribution from Stripe
  - Record admin.tenant_viewed audit event

- [X] T023 [US3] Add GET /admin/tenants/{tenant_id} endpoint in backend/app/modules/admin/router.py
  - Return TenantDetailResponse per contracts/openapi.yaml
  - Use require_admin() dependency
  - Handle not found with 404

- [X] T024 [P] [US3] Create TenantDetailCard component in frontend/src/app/(protected)/internal/admin/components/TenantDetailCard.tsx
  - Account info section (name, email, dates)
  - Billing section (Stripe IDs, next billing date)
  - Usage section (clients, AI queries, documents)

- [X] T025 [P] [US3] Create SubscriptionHistory component in frontend/src/app/(protected)/internal/admin/components/SubscriptionHistory.tsx
  - Timeline of billing events
  - Show tier changes, credits applied
  - Display reason/notes for each event

- [X] T026 [US3] Create tenant detail page in frontend/src/app/(protected)/internal/admin/customers/[id]/page.tsx
  - Use useTenant hook with tenant_id param
  - Render TenantDetailCard and SubscriptionHistory
  - Add action buttons for tier change, credits (links to US4)
  - Show feature flags section (links to US5)

**Checkpoint**: User Story 3 complete - tenant detail view functional

---

## Phase 6: User Story 4 - Manage Subscriptions (Priority: P2)

**Goal**: Operators can change tiers and apply credits with full audit trail

**Independent Test**: Change a tenant's tier and verify change in both database and Stripe; apply credit and verify in Stripe

### Implementation for User Story 4

- [X] T027 [US4] Add change_tier service method in backend/app/modules/admin/service.py
  - Validate tier change (check client count for downgrades)
  - Call Stripe to update subscription
  - Update tenant.tier in database
  - Create BillingEvent with admin.tier_changed type
  - Handle Stripe errors with retry queue

- [X] T028 [US4] Add apply_credit service method in backend/app/modules/admin/service.py
  - Validate credit amount and type
  - Apply credit to Stripe customer balance (one-time) or create coupon (recurring)
  - Create BillingEvent with admin.credit_applied type

- [X] T029 [US4] Add subscription management endpoints in backend/app/modules/admin/router.py
  - PUT /admin/tenants/{tenant_id}/tier per contracts/openapi.yaml
  - POST /admin/tenants/{tenant_id}/credit per contracts/openapi.yaml
  - Handle 409 Conflict for excess clients downgrade

- [X] T030 [P] [US4] Create TierChangeModal component in frontend/src/app/(protected)/internal/admin/components/TierChangeModal.tsx
  - Current tier display
  - New tier selector dropdown
  - Reason textarea (required, min 10 chars)
  - Warning for downgrade with excess clients
  - Confirm button with loading state

- [X] T031 [P] [US4] Create CreditModal component in frontend/src/app/(protected)/internal/admin/components/CreditModal.tsx
  - Amount input (in dollars, convert to cents)
  - Credit type selector (one-time/recurring)
  - Reason textarea (required)
  - Confirm button with loading state

- [X] T032 [US4] Wire tier change and credit modals in tenant detail page
  - Update frontend/src/app/(protected)/internal/admin/customers/[id]/page.tsx
  - Add "Change Tier" button that opens TierChangeModal
  - Add "Apply Credit" button that opens CreditModal
  - Show success/error toasts after mutations

**Checkpoint**: User Story 4 complete - subscription management functional

---

## Phase 7: User Story 5 - Configure Feature Flags (Priority: P3)

**Goal**: Operators can override feature flags for individual tenants

**Independent Test**: Override a feature flag for a tenant and verify the feature behavior changes immediately

### Implementation for User Story 5

- [X] T033 [US5] Add feature flag service methods in backend/app/modules/admin/service.py
  - `get_tenant_feature_flags(tenant_id)` - tier defaults merged with overrides
  - `set_feature_flag_override(tenant_id, feature_key, value, reason, admin_id)`
  - `delete_feature_flag_override(tenant_id, feature_key)`
  - Create BillingEvent with admin.flag_overridden type

- [X] T034 [US5] Update feature_flags.py to check overrides in backend/app/core/feature_flags.py
  - Add `get_tenant_feature_value(tenant_id, feature_key, session)` function
  - Check FeatureFlagOverride table first
  - Fall back to tier default
  - Cache result per-request

- [X] T035 [US5] Add feature flag endpoints in backend/app/modules/admin/router.py
  - GET /admin/tenants/{tenant_id}/features
  - PUT /admin/tenants/{tenant_id}/features/{feature_key}
  - DELETE /admin/tenants/{tenant_id}/features/{feature_key}

- [X] T036 [P] [US5] Create FeatureFlagOverrides component in frontend/src/app/(protected)/internal/admin/components/FeatureFlagOverrides.tsx
  - Table with columns: feature, tier default, override, effective value
  - Toggle switches for each feature
  - Visual distinction for overridden flags (badge/highlight)
  - Reason input modal when toggling

- [X] T037 [US5] Add feature flags section to tenant detail page
  - Update frontend/src/app/(protected)/internal/admin/customers/[id]/page.tsx
  - Render FeatureFlagOverrides component
  - Handle mutations with success/error toasts

**Checkpoint**: User Story 5 complete - feature flag overrides functional

---

## Phase 8: User Story 6 - View Usage Analytics (Priority: P3)

**Goal**: Operators can see aggregate usage metrics across all tenants

**Independent Test**: View usage analytics and verify metrics match expected aggregates

### Implementation for User Story 6

- [X] T038 [US6] Add aggregate usage methods to AdminDashboardService
  - Update backend/app/modules/admin/service.py
  - `get_platform_usage(tier_filter, start_date, end_date)`
  - `get_top_users(metric, limit)` - top by clients/syncs/AI queries
  - Aggregate from existing usage snapshots

- [X] T039 [US6] Add usage analytics endpoints in backend/app/modules/admin/router.py
  - GET /admin/usage/analytics - aggregate metrics
  - GET /admin/usage/top-users - top users by metric
  - Extend existing /admin/usage/* endpoints if needed

- [X] T040 [P] [US6] Create UsageAnalytics component in frontend/src/app/(protected)/internal/admin/components/UsageAnalytics.tsx
  - Cards for total clients, syncs, AI queries
  - Tier breakdown bar chart
  - Date range selector

- [X] T041 [P] [US6] Create TopUsersTable component in frontend/src/app/(protected)/internal/admin/components/TopUsersTable.tsx
  - Table with tenant name and metric value
  - Metric selector (clients, syncs, AI usage)
  - Link to tenant detail

- [X] T042 [US6] Add usage analytics to admin dashboard
  - Created dedicated /internal/admin/analytics page
  - Added Analytics to admin navigation
  - Renders UsageAnalytics and TopUsersTable components

**Checkpoint**: All user stories complete - full admin dashboard functional

---

## Phase 9: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [X] T043 [P] Add audit logging for dashboard access
  - Logging via structlog in router.py for all admin operations
  - Admin user ID logged for all sensitive operations

- [ ] T044 [P] Add rate limiting to admin endpoints
  - 60 requests/minute per admin user
  - Deferred to future iteration (not critical for internal tool)

- [X] T045 [P] Add self-modification block validation
  - Prevent admins from modifying their own tenant
  - SelfModificationBlockedError in service.py
  - Checked in tier change, credit, and feature flag operations

- [X] T046 Performance optimization for large tenant lists
  - Database indexes already added in migration
  - Pagination implemented in repository.py

- [X] T047 [P] Add loading skeletons to frontend components
  - TenantTable loading skeleton
  - RevenueMetrics loading skeleton
  - TenantDetailCard loading skeleton
  - All components include skeleton states

- [X] T048 Update module exports in backend/app/modules/admin/__init__.py
  - All models, schemas, services properly importable
  - Clean module interface

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `cd backend && uv run pytest tests/unit/modules/admin/ -v`
  - Run: `cd frontend && npm run test`

- [ ] TFINAL-2 Run linting and type checking
  - Run: `cd backend && uv run ruff check . && uv run mypy app/modules/admin/`
  - Run: `cd frontend && npm run lint`

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/022-admin-dashboard`
  - Run: `gh pr create --title "Spec 022: Admin Dashboard (Internal)" --body "..."`
  - Include summary of all 6 user stories in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 022 as COMPLETE
  - Update current focus to next spec (023)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first - creates feature branch
- **Setup (Phase 1)**: Creates models and schemas - BLOCKS Phase 2
- **Foundational (Phase 2)**: Repository/service/frontend foundation - BLOCKS all user stories
- **User Stories (Phase 3-8)**: All depend on Phase 2 completion
  - US1 & US2 (both P1): Can run in parallel
  - US3 & US4 (both P2): Can run in parallel after US1
  - US5 & US6 (both P3): Can run in parallel after US3
- **Polish (Phase 9)**: Depends on all user stories complete

### User Story Dependencies

| Story | Depends On | Can Parallel With |
|-------|-----------|-------------------|
| US1 (View Customers) | Phase 2 | US2 |
| US2 (Revenue Metrics) | Phase 2 | US1 |
| US3 (Tenant Details) | US1 (for navigation) | US4 |
| US4 (Subscriptions) | US3 (for UI context) | US5 |
| US5 (Feature Flags) | Phase 2 | US6 |
| US6 (Usage Analytics) | Phase 2 | US5 |

### Within Each User Story

- Backend service method → endpoint → frontend component → page integration

### Parallel Opportunities

- T001, T002, T004: All schema/model creation (Phase 1)
- T008, T009, T010: Frontend foundation (Phase 2)
- T013: TenantTable independent of backend
- T018, T019: Revenue components independent
- T024, T025: Detail view components independent
- T030, T031: Modal components independent
- T036: FeatureFlagOverrides independent
- T040, T041: Analytics components independent

---

## Parallel Example: Phase 1 Setup

```bash
# Launch all Phase 1 tasks in parallel:
Task: "T001 [P] Create admin domain exceptions in backend/app/modules/admin/exceptions.py"
Task: "T002 [P] Create FeatureFlagOverride model in backend/app/modules/admin/models.py"
Task: "T004 [P] Extend admin schemas in backend/app/modules/admin/schemas.py"
```

---

## Implementation Strategy

### MVP First (User Story 1 Only)

1. Complete Phase 1: Setup (T001-T004)
2. Complete Phase 2: Foundational (T005-T010)
3. Complete Phase 3: User Story 1 (T011-T015)
4. **STOP and VALIDATE**: Test tenant list independently
5. Deploy/demo if ready

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add US1 → Tenant list works → Deploy
3. Add US2 → Revenue metrics → Deploy
4. Add US3 + US4 → Tenant management → Deploy
5. Add US5 + US6 → Feature flags + Analytics → Deploy
6. Polish → Final QA → Merge to main

### Parallel Team Strategy

With multiple developers:
1. Team completes Setup + Foundational together
2. Once Phase 2 is done:
   - Developer A: US1 (Tenant List) + US3 (Details)
   - Developer B: US2 (Revenue) + US4 (Subscriptions)
   - Developer C: US5 (Feature Flags) + US6 (Analytics)
3. Stories complete and integrate independently

---

## Summary

| Metric | Value |
|--------|-------|
| Total Tasks | 48 |
| Setup Tasks | 4 |
| Foundational Tasks | 6 |
| US1 Tasks | 5 |
| US2 Tasks | 6 |
| US3 Tasks | 5 |
| US4 Tasks | 6 |
| US5 Tasks | 5 |
| US6 Tasks | 5 |
| Polish Tasks | 6 |
| PR/Merge Tasks | 6 |
| Parallel Opportunities | 20+ tasks marked [P] |

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story for traceability
- Each user story should be independently completable and testable
- Commit after each task or logical group
- Stop at any checkpoint to validate story independently
- Tests not included (not explicitly requested in spec)
