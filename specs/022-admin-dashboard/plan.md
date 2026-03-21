# Implementation Plan: Admin Dashboard (Internal)

**Branch**: `feature/022-admin-dashboard` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/022-admin-dashboard/spec.md`

## Summary

Build an internal admin dashboard for Clairo operators to manage tenants, monitor revenue metrics (MRR, churn, expansion), handle subscription changes, and configure per-tenant feature flag overrides. The dashboard extends the existing admin module with customer management, revenue analytics, and subscription administration capabilities.

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, Next.js 14, shadcn/ui, TanStack Query
**Storage**: PostgreSQL 16 (existing), Redis (caching)
**Testing**: pytest with pytest-asyncio (backend), Vitest (frontend)
**Target Platform**: Web application (internal admin users only)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Dashboard load < 3 seconds, metrics calculation < 5 seconds, 500+ tenants support
**Constraints**: Admin-only access, full audit logging, Stripe sync within 10 seconds
**Scale/Scope**: ~500 tenants initially, all admin operations audited

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Evidence |
|-----------|--------|----------|
| Modular Monolith | ✅ PASS | Extends existing `admin` module at `backend/app/modules/admin/` |
| Repository Pattern | ✅ PASS | Will use repositories for all DB access (AdminRepository, FeatureFlagOverrideRepository) |
| Multi-tenancy | ✅ PASS | Admin endpoints bypass tenant RLS intentionally for cross-tenant queries |
| Testing Strategy | ✅ PASS | Unit tests for services, integration tests for endpoints, audit event tests |
| Audit-First | ✅ PASS | All admin actions logged per FR-002, FR-017, FR-021 |
| Pydantic Schemas | ✅ PASS | All request/response models as Pydantic v2 |
| Type Hints | ✅ PASS | All functions fully typed |
| Domain Exceptions | ✅ PASS | AdminError hierarchy, HTTPException only in router |

**Gate Status**: ✅ PASSED - No violations

## Project Structure

### Documentation (this feature)

```text
specs/022-admin-dashboard/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── openapi.yaml     # Admin API endpoints
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── admin/
│           ├── __init__.py          # Module exports
│           ├── router.py            # API endpoints (extend existing)
│           ├── service.py           # Business logic (new)
│           ├── schemas.py           # Pydantic schemas (extend existing)
│           ├── repository.py        # DB access (new)
│           ├── models.py            # SQLAlchemy models (new)
│           ├── exceptions.py        # Domain exceptions (new)
│           └── usage_service.py     # Existing usage service
└── tests/
    ├── unit/
    │   └── modules/
    │       └── admin/
    │           ├── test_service.py
    │           └── test_repository.py
    └── integration/
        └── api/
            └── test_admin.py

frontend/
├── src/
│   ├── app/
│   │   └── (protected)/
│   │       └── internal/
│   │           └── admin/
│   │               ├── page.tsx          # Dashboard overview
│   │               ├── layout.tsx        # Admin layout
│   │               ├── customers/
│   │               │   ├── page.tsx      # Tenant list
│   │               │   └── [id]/
│   │               │       └── page.tsx  # Tenant detail
│   │               ├── revenue/
│   │               │   └── page.tsx      # Revenue metrics
│   │               └── components/
│   │                   ├── TenantTable.tsx
│   │                   ├── RevenueMetrics.tsx
│   │                   ├── TierChangeModal.tsx
│   │                   ├── CreditModal.tsx
│   │                   └── FeatureFlagOverrides.tsx
│   ├── hooks/
│   │   └── useAdminDashboard.ts
│   └── lib/
│       └── api/
│           └── admin.ts              # Admin API client
└── src/__tests__/
    └── admin/
        └── TenantTable.test.tsx
```

**Structure Decision**: Extends existing modular monolith pattern. Admin module already exists at `backend/app/modules/admin/` - we add new files alongside existing `usage_service.py`. Frontend uses `/internal/admin/` path to distinguish from customer-facing admin features.

## Complexity Tracking

> No constitution violations to justify.

## Completed Planning Phases

### Phase 0: Research ✅

**Status**: Complete
**Output**: [research.md](./research.md)

Findings:
- Use existing `require_admin()` dependency for authentication
- Extend `BillingEvent` model for admin-initiated events
- Create new `FeatureFlagOverride` model for per-tenant overrides
- Calculate revenue metrics on-demand with Redis caching

### Phase 1: Design & Contracts ✅

**Status**: Complete
**Outputs**:
- [data-model.md](./data-model.md) - Entity definitions
- [contracts/openapi.yaml](./contracts/openapi.yaml) - API specification
- [quickstart.md](./quickstart.md) - Developer guide

Key Design Decisions:
- New table: `feature_flag_overrides` for per-tenant overrides
- 15 API endpoints across 4 categories (tenants, revenue, subscriptions, flags)
- Stripe sync for tier changes with proration
- Admin actions audited via extended BillingEvent

## Implementation Phases

### Phase 1: Backend Foundation
- Add new models (BillingEvent enhancement, FeatureFlagOverride)
- Create AdminRepository and AdminService
- Implement tenant list/detail endpoints
- Add revenue metrics calculation

### Phase 2: Subscription Management
- Implement tier change endpoint with Stripe sync
- Implement credit application endpoint
- Add audit logging for all billing changes

### Phase 3: Feature Flags
- Create FeatureFlagOverrideRepository
- Implement override CRUD endpoints
- Integrate with existing feature flag system

### Phase 4: Frontend Dashboard
- Create admin layout and navigation
- Implement tenant list with search/filter/sort
- Implement tenant detail view
- Add revenue metrics dashboard

### Phase 5: Frontend Operations
- Implement tier change modal
- Implement credit application modal
- Implement feature flag override UI

### Phase 6: Testing & Polish
- Unit tests for services
- Integration tests for endpoints
- E2E test for critical flows
- Performance optimization for large tenant lists
