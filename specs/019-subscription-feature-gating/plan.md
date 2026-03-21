# Implementation Plan: Subscription & Feature Gating

**Branch**: `019-subscription-feature-gating` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/019-subscription-feature-gating/spec.md`

## Summary

Implement paid subscription system with Stripe integration and tier-based feature gating. Tenants subscribe to one of four tiers (Starter/Professional/Growth/Enterprise), each with defined client limits and feature access. Backend enforces gating via decorators, frontend via hooks. Existing tenants are migrated to Professional tier with "grandfathered" status (no payment required).

## Technical Context

**Language/Version**: Python 3.12 (backend), TypeScript 5.x (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Stripe SDK, React 18, Next.js 14
**Storage**: PostgreSQL 16 (existing), new billing_events table
**Testing**: pytest with pytest-asyncio (backend), Jest/RTL (frontend)
**Target Platform**: Linux server (AWS ECS), Browser (React SPA)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Checkout redirect <3s, feature check <10ms, webhook processing <500ms
**Constraints**: PCI compliance via Stripe (no card data handling), Australian data residency
**Scale/Scope**: ~50 tenants initially, ~500 clients total, ~10 billing events/day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Monolith | ✅ PASS | New `billing` module under `modules/` |
| Repository Pattern | ✅ PASS | BillingEventRepository for database access |
| Test-First Development | ✅ PASS | Tests required before implementation |
| Type Hints | ✅ PASS | All code fully typed |
| Pydantic Schemas | ✅ PASS | All API schemas are Pydantic models |
| Domain Exceptions | ✅ PASS | FeatureNotAvailableError, ClientLimitExceededError |
| Async/Await | ✅ PASS | All I/O operations async |
| Multi-Tenancy | ✅ PASS | Billing events scoped by tenant_id |
| Auditing | ✅ PASS | All billing events logged with audit trail |

**Gate Status**: ✅ PASSED - All constitution principles satisfied

## Project Structure

### Documentation (this feature)

```text
specs/019-subscription-feature-gating/
├── spec.md              # User-centric specification
├── plan.md              # This file
├── research.md          # Technical decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer setup guide
├── contracts/           # API specifications
│   └── subscription-api.yaml
├── checklists/          # Quality validation
│   └── requirements.md
└── tasks.md             # Task list (Phase 2 output)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── core/
│   │   └── feature_flags.py          # NEW: Tier config, gating helpers
│   │
│   ├── modules/
│   │   ├── auth/
│   │   │   ├── models.py             # MODIFIED: Tenant + subscription fields
│   │   │   └── schemas.py            # MODIFIED: TenantResponse + tier info
│   │   │
│   │   └── billing/                  # NEW MODULE
│   │       ├── __init__.py
│   │       ├── models.py             # BillingEvent model
│   │       ├── schemas.py            # Request/Response schemas
│   │       ├── repository.py         # Database access
│   │       ├── service.py            # Business logic
│   │       ├── router.py             # API endpoints
│   │       ├── stripe_client.py      # Stripe integration
│   │       ├── webhooks.py           # Webhook handlers
│   │       └── exceptions.py         # Domain exceptions
│   │
│   └── alembic/versions/
│       └── 023_subscription_feature_gating.py  # NEW: Migration
│
└── tests/
    ├── unit/
    │   └── modules/billing/
    │       ├── test_feature_flags.py
    │       ├── test_service.py
    │       └── test_stripe_client.py
    └── integration/
        └── api/
            ├── test_subscription.py
            └── test_feature_gating.py

frontend/
├── src/
│   ├── hooks/
│   │   └── useTier.ts                # NEW: Tier access hook
│   │
│   ├── components/
│   │   └── billing/                  # NEW: Billing components
│   │       ├── UpgradePrompt.tsx     # Feature gate UI
│   │       ├── PricingTable.tsx      # Tier comparison
│   │       ├── SubscriptionCard.tsx  # Current plan display
│   │       └── ClientUsageBar.tsx    # Usage indicator
│   │
│   ├── lib/api/
│   │   └── billing.ts                # NEW: API client
│   │
│   ├── types/
│   │   └── billing.ts                # NEW: TypeScript types
│   │
│   └── app/
│       └── (protected)/
│           └── settings/
│               └── billing/
│                   └── page.tsx      # NEW: Billing settings page
│
└── tests/
    └── components/billing/
        ├── UpgradePrompt.test.tsx
        └── PricingTable.test.tsx
```

**Structure Decision**: Web application pattern with backend `billing` module and frontend `billing` components. Extends existing auth module for Tenant model changes.

## Phase 0: Research Summary

See [research.md](./research.md) for full details.

### Key Decisions

| Topic | Decision | Rationale |
|-------|----------|-----------|
| Payment Processing | Stripe Checkout | PCI-compliant, hosted checkout |
| Billing Portal | Stripe Customer Portal | Self-service without custom UI |
| Feature Config | Static Python dict | Simple, fast, version-controlled |
| Backend Gating | FastAPI decorators | Consistent with existing patterns |
| Frontend Gating | React hook (useTier) | Ergonomic, single source of truth |
| Client Tracking | Database trigger | Accurate, no app-level sync issues |
| Webhook Processing | Idempotent with event_id | Handles Stripe retries |

### Dependencies

- Stripe Python SDK: `stripe>=7.0.0`
- Existing: FastAPI, SQLAlchemy, Pydantic, Clerk

## Phase 1: Design Summary

See [data-model.md](./data-model.md) for entity definitions.
See [contracts/subscription-api.yaml](./contracts/subscription-api.yaml) for API specification.

### Entities

| Entity | Type | Description |
|--------|------|-------------|
| Tenant | Extended | Add tier, stripe_customer_id, client_count |
| SubscriptionTier | Enum | starter, professional, growth, enterprise |
| SubscriptionStatus | Enum | Add grandfathered, past_due values |
| BillingEvent | New | Audit trail for all billing events |
| TIER_FEATURES | Config | Static feature-to-tier mapping |

### API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | /subscription | Get current subscription |
| POST | /subscription/checkout | Create Stripe checkout session |
| POST | /subscription/portal | Create billing portal session |
| POST | /subscription/upgrade | Immediate tier upgrade |
| POST | /subscription/downgrade | Scheduled tier downgrade |
| POST | /subscription/cancel | Cancel subscription |
| GET | /features | Get feature access status |
| GET | /features/tiers | List all tiers with pricing |
| GET | /billing/events | List billing events |
| POST | /webhooks/stripe | Stripe webhook handler |

### Frontend Components

| Component | Purpose |
|-----------|---------|
| useTier() | Hook for tier info and feature checks |
| UpgradePrompt | Shown when accessing gated features |
| PricingTable | Tier comparison for checkout |
| SubscriptionCard | Current plan in settings |
| ClientUsageBar | Usage vs limit indicator |

## Migration Strategy

1. **Database Migration**:
   - Add new columns to tenants table
   - Create billing_events table
   - Create subscription_tier and billing_event_status enums
   - Add client count trigger

2. **Data Migration**:
   - Set all existing tenants to tier='professional', status='grandfathered'
   - Initialize client_count from xero_connections

3. **Feature Rollout**:
   - Deploy backend with gating in "log-only" mode first
   - Verify no false positives
   - Enable enforcement after validation

## Testing Strategy

| Test Type | Coverage | Scope |
|-----------|----------|-------|
| Unit Tests | 80% | Feature flags, service logic, Stripe client |
| Integration | 100% | All API endpoints |
| Contract | 100% | Stripe webhook signatures |
| E2E | Critical | Checkout flow, feature gating |

### Critical Test Scenarios

1. New tenant completes checkout → tier assigned correctly
2. Starter tenant blocked from Professional features
3. Upgrade proration calculated correctly
4. Webhook failure → retry succeeds
5. Grandfathered tenant has full access
6. Client limit blocks new client creation

## Complexity Tracking

> No complexity violations - all patterns are standard for the codebase.

| Pattern | Justification |
|---------|---------------|
| New billing module | Required for subscription domain |
| Stripe integration | External dependency for payments |
| Database trigger | Ensures accurate client counts |

## Next Steps

1. Run `/speckit.tasks` to generate task list
2. Create feature branch: `git checkout -b feature/019-subscription-feature-gating`
3. Implement in task order (tests first)
4. Create PR for review

## References

- [spec.md](./spec.md) - Feature specification
- [research.md](./research.md) - Technical research
- [data-model.md](./data-model.md) - Entity definitions
- [quickstart.md](./quickstart.md) - Developer setup
- [contracts/subscription-api.yaml](./contracts/subscription-api.yaml) - API specification
