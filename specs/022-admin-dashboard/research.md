# Research: Admin Dashboard (Internal)

**Feature Branch**: `feature/022-admin-dashboard`
**Created**: 2026-01-01
**Phase**: 0 (Research)

## Overview

This document captures research findings and design decisions for the Admin Dashboard feature. The spec had no NEEDS CLARIFICATION markers - all requirements were well-defined.

## Existing Patterns Analysis

### 1. Admin Authentication

**Decision**: Use existing `require_admin()` dependency from `app.modules.auth.permissions`

**Rationale**:
- Already implemented and tested in Spec 020
- Provides role-based access control (admin/super_admin)
- Consistent with existing admin endpoints

**Evidence**: `backend/app/modules/admin/router.py:73` uses `Depends(require_admin())`

### 2. Billing Event Storage

**Decision**: Extend existing `BillingEvent` model for admin-initiated events

**Rationale**:
- Model already exists at `backend/app/modules/billing/models.py:44`
- Has `event_type` field that can accommodate admin events (tier_change, credit_applied)
- Includes `event_data` JSONB for flexible metadata

**Alternatives Considered**:
- New AdminEvent table: Rejected - duplicates structure, complicates queries
- Separate AdminAuditLog: Rejected - BillingEvent already serves audit purpose

### 3. Feature Flag Override Storage

**Decision**: Create new `FeatureFlagOverride` model in admin module

**Rationale**:
- Current feature flags are tier-based (static configuration in `core/feature_flags.py`)
- Per-tenant overrides require database storage
- Admin module is the logical owner

**Implementation**:
- New table: `feature_flag_overrides`
- Fields: tenant_id, feature_key, override_value (enabled/disabled/null), reason, created_by, created_at
- Query pattern: Check override first, fall back to tier default

### 4. Revenue Metrics Calculation

**Decision**: Calculate on-demand from Stripe data with Redis caching

**Rationale**:
- MRR accuracy requires real-time subscription data
- Stripe is source of truth for billing
- Cache with 5-minute TTL balances freshness vs performance

**Implementation Approach**:
1. Query active subscriptions from Stripe API
2. Aggregate by status, tier, and date range
3. Calculate:
   - MRR = Sum of active subscription amounts
   - Churn = Lost MRR / Starting MRR
   - Expansion = Upgrades - Downgrades
4. Cache results in Redis

### 5. Tenant List Performance

**Decision**: Use server-side pagination with database-level filtering

**Rationale**:
- Spec requires support for 500+ tenants
- Must load in < 3 seconds
- Existing `AdminUsageService` patterns work well

**Implementation**:
- Single SQL query with LIMIT/OFFSET
- Database indexes on frequently filtered columns
- Return subset with total count for pagination

### 6. Stripe Tier Change Sync

**Decision**: Use Stripe's subscription update API with proration

**Rationale**:
- Spec requires changes propagate within 10 seconds
- Stripe handles proration automatically
- Existing `StripeClient` at `billing/stripe_client.py` can be extended

**Implementation**:
1. Validate tier change is allowed
2. Call Stripe API to update subscription
3. Record BillingEvent with audit trail
4. Emit domain event for cache invalidation

### 7. Credit Application

**Decision**: Use Stripe customer balance credits

**Rationale**:
- Credits appear on next invoice automatically
- Stripe maintains credit balance
- Supports both one-time and recurring via metadata

**Implementation**:
- One-time: Add to customer balance
- Recurring: Create coupon with duration

## Technology Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Revenue cache | Redis | Existing infrastructure, 5-min TTL |
| Audit logging | BillingEvent table | Existing pattern, 7-year retention |
| Admin access | require_admin() | Existing dependency, role-based |
| Stripe sync | stripe.Subscription.modify | Standard API, proration support |

## Performance Considerations

1. **Tenant List Query**: Add composite index on (tier, created_at, is_active)
2. **Revenue Metrics**: Cache with 5-minute TTL, async refresh
3. **Feature Flag Lookup**: Single query per tenant, result cached per-request

## Security Considerations

1. **Admin-only access**: All endpoints protected by `require_admin()`
2. **Audit trail**: Every action logged with operator_id, timestamp, reason
3. **Self-modification block**: Operators cannot modify their own tenant
4. **Rate limiting**: 60 requests/minute per admin user

## Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| FastAPI | existing | API framework |
| SQLAlchemy 2.x | existing | ORM |
| Stripe SDK | existing | Billing API |
| Redis | existing | Caching |
| structlog | existing | Audit logging |

## Risks and Mitigations

| Risk | Mitigation |
|------|------------|
| Stripe API downtime | Queue tier changes, retry with exponential backoff |
| Large tenant lists | Server-side pagination, database indexes |
| Revenue calculation accuracy | Use Stripe as source of truth, cache with short TTL |
| Feature flag conflicts | Explicit overrides always win over tier defaults |

## Next Steps

- Phase 1: Create data models and API contracts
- Phase 2: Implement backend foundation
- Phase 3: Build frontend dashboard
