# Research: Subscription & Feature Gating

**Date**: 2025-12-31
**Spec**: 019-subscription-feature-gating

## Research Tasks Completed

### 1. Stripe Integration Pattern

**Decision**: Use Stripe Checkout for payment collection and Stripe Customer Portal for self-service management.

**Rationale**:
- Stripe Checkout is PCI-compliant out of the box - no need to handle card data
- Customer Portal provides self-service billing without custom UI
- Webhooks ensure real-time sync of subscription state
- Native support for prorated upgrades and scheduled downgrades

**Alternatives Considered**:
- Custom payment form with Stripe Elements: More control but higher PCI compliance burden
- PayPal integration: Less developer-friendly, higher fees in Australia
- Direct bank integration: Too complex for initial release

**Implementation Pattern**:
```python
# Backend creates Checkout Session, returns URL
session = stripe.checkout.Session.create(
    customer=stripe_customer_id,
    mode='subscription',
    line_items=[{'price': price_id, 'quantity': 1}],
    success_url=f'{frontend_url}/billing/success',
    cancel_url=f'{frontend_url}/billing/cancel',
)

# Frontend redirects to Stripe-hosted checkout
window.location.href = session.url

# Webhooks update local subscription state
@app.post("/webhooks/stripe")
async def stripe_webhook(request: Request):
    event = stripe.Webhook.construct_event(...)
    if event.type == "customer.subscription.updated":
        await update_tenant_subscription(event.data.object)
```

---

### 2. Feature Flag Configuration Pattern

**Decision**: Static Python configuration with tier-to-features mapping, loaded at startup.

**Rationale**:
- Simple, fast, and testable
- No external service dependency
- Easy to version control and review changes
- Can evolve to database-driven later if needed

**Alternatives Considered**:
- LaunchDarkly/Feature flag service: Overkill for tier-based gating
- Database-driven flags: Adds complexity, slower reads
- Environment variables: Hard to manage multiple tiers

**Implementation Pattern**:
```python
# app/core/feature_flags.py
TIER_FEATURES = {
    "starter": {
        "max_clients": 25,
        "ai_insights": "basic",  # Limited analyzers
        "client_portal": False,
        "custom_triggers": False,
        "api_access": False,
        "knowledge_base": False,
        "magic_zone": False,
    },
    "professional": {
        "max_clients": 100,
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": False,
        "knowledge_base": True,
        "magic_zone": True,
    },
    "growth": {
        "max_clients": 250,
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": True,
        "knowledge_base": True,
        "magic_zone": True,
    },
    "enterprise": {
        "max_clients": None,  # Unlimited
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": True,
        "knowledge_base": True,
        "magic_zone": True,
    },
}
```

---

### 3. Backend Gating Decorator Pattern

**Decision**: FastAPI dependency injection with custom decorators for feature and tier checks.

**Rationale**:
- Consistent with existing FastAPI patterns in codebase
- Decorators are explicit and easy to audit
- Dependency injection allows easy testing/mocking
- Error responses are standardized

**Alternatives Considered**:
- Middleware-based gating: Too coarse, can't gate individual endpoints
- Manual checks in each endpoint: Repetitive, error-prone
- Permission-based RBAC extension: Conflates roles with features

**Implementation Pattern**:
```python
# Decorator approach
from functools import wraps
from fastapi import HTTPException, status

def require_feature(feature_name: str):
    """Decorator to require a specific feature."""
    def decorator(func):
        @wraps(func)
        async def wrapper(*args, tenant: Tenant = Depends(get_current_tenant), **kwargs):
            if not has_feature(tenant.tier, feature_name):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail={
                        "error": "feature_not_available",
                        "feature": feature_name,
                        "required_tier": get_minimum_tier(feature_name),
                        "current_tier": tenant.tier,
                    }
                )
            return await func(*args, tenant=tenant, **kwargs)
        return wrapper
    return decorator

# Usage
@router.post("/triggers")
@require_feature("custom_triggers")
async def create_trigger(data: TriggerCreate, tenant: Tenant = Depends(get_current_tenant)):
    ...
```

---

### 4. Frontend Gating Hook Pattern

**Decision**: React hook `useTier()` that provides tier info and feature access checks.

**Rationale**:
- Consistent with React patterns
- Single source of truth for tier state
- Easy to use in conditional rendering
- Supports both feature checks and limit checks

**Alternatives Considered**:
- Redux global state: Overkill, Zustand is already in use
- Context-only: Less ergonomic for feature checks
- HOC pattern: Outdated, hooks are preferred

**Implementation Pattern**:
```typescript
// hooks/useTier.ts
export function useTier() {
  const { user } = useUser();  // From Clerk
  const tenant = useTenantStore((state) => state.tenant);

  const canAccess = useCallback((feature: FeatureName): boolean => {
    if (!tenant?.tier) return false;
    return TIER_FEATURES[tenant.tier]?.[feature] ?? false;
  }, [tenant?.tier]);

  const clientLimit = useMemo(() => {
    if (!tenant?.tier) return 0;
    return TIER_FEATURES[tenant.tier]?.max_clients ?? 0;
  }, [tenant?.tier]);

  return {
    tier: tenant?.tier ?? 'starter',
    subscriptionStatus: tenant?.subscription_status,
    canAccess,
    clientLimit,
    clientCount: tenant?.client_count ?? 0,
    isAtLimit: (tenant?.client_count ?? 0) >= clientLimit,
    isApproachingLimit: (tenant?.client_count ?? 0) >= clientLimit * 0.8,
  };
}

// Usage in components
function TriggerManager() {
  const { canAccess, tier } = useTier();

  if (!canAccess('custom_triggers')) {
    return <UpgradePrompt feature="custom_triggers" requiredTier="professional" />;
  }

  return <TriggerList />;
}
```

---

### 5. Tenant Model Extension

**Decision**: Add subscription fields to existing Tenant model, create new billing tables.

**Rationale**:
- Extends existing auth model without breaking changes
- Billing data separated for clean domain boundaries
- Migration is straightforward with defaults

**Changes to Tenant**:
```python
class SubscriptionTier(str, enum.Enum):
    STARTER = "starter"
    PROFESSIONAL = "professional"
    GROWTH = "growth"
    ENTERPRISE = "enterprise"

# New fields on Tenant:
tier: SubscriptionTier = SubscriptionTier.PROFESSIONAL  # Default for migration
stripe_customer_id: str | None = None
stripe_subscription_id: str | None = None
subscription_status: SubscriptionStatus  # Already exists, reuse
current_period_end: datetime | None = None
client_count: int = 0  # Denormalized for fast access
```

---

### 6. Client Count Tracking Strategy

**Decision**: Denormalized count on Tenant model, updated via database trigger on XeroConnection.

**Rationale**:
- Fast reads for limit checks (no joins)
- Database trigger ensures accuracy
- Works even if app crashes during client creation

**Alternatives Considered**:
- Count on every request: Too slow
- Cached count in Redis: Additional complexity, sync issues
- Materialized view: Overkill for simple count

**Implementation**:
```sql
-- Trigger to update client_count on tenant
CREATE OR REPLACE FUNCTION update_tenant_client_count()
RETURNS TRIGGER AS $$
BEGIN
  IF TG_OP = 'INSERT' THEN
    UPDATE tenants SET client_count = client_count + 1 WHERE id = NEW.tenant_id;
  ELSIF TG_OP = 'DELETE' THEN
    UPDATE tenants SET client_count = client_count - 1 WHERE id = OLD.tenant_id;
  END IF;
  RETURN NULL;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_client_count
AFTER INSERT OR DELETE ON xero_connections
FOR EACH ROW EXECUTE FUNCTION update_tenant_client_count();
```

---

### 7. Webhook Handling Strategy

**Decision**: Async webhook processing with idempotency and failure handling.

**Rationale**:
- Stripe webhooks may be delivered multiple times
- Processing must be idempotent
- Failed processing should not block response
- Events should be logged for debugging

**Implementation Pattern**:
```python
@router.post("/webhooks/stripe")
async def stripe_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    payload = await request.body()
    sig_header = request.headers.get("stripe-signature")

    try:
        event = stripe.Webhook.construct_event(
            payload, sig_header, settings.stripe_webhook_secret
        )
    except stripe.SignatureVerificationError:
        raise HTTPException(400, "Invalid signature")

    # Idempotency check
    existing = await db.execute(
        select(BillingEvent).where(BillingEvent.stripe_event_id == event.id)
    )
    if existing.scalar_one_or_none():
        return {"status": "already_processed"}

    # Process event
    await process_stripe_event(db, event)

    return {"status": "success"}
```

---

### 8. Migration Strategy for Existing Tenants

**Decision**: Default all existing tenants to Professional tier with "grandfathered" status.

**Rationale**:
- No disruption to existing users
- Professional tier matches current feature set
- Grandfathered status distinguishes from paying customers
- Allows optional conversion to paid plan

**Migration SQL**:
```sql
-- Add new columns with defaults
ALTER TABLE tenants
  ADD COLUMN tier VARCHAR(20) DEFAULT 'professional',
  ADD COLUMN stripe_customer_id VARCHAR(255),
  ADD COLUMN stripe_subscription_id VARCHAR(255),
  ADD COLUMN current_period_end TIMESTAMPTZ,
  ADD COLUMN client_count INTEGER DEFAULT 0;

-- Update subscription_status for existing tenants
UPDATE tenants
SET subscription_status = 'grandfathered'
WHERE subscription_status = 'trial';

-- Initialize client_count from xero_connections
UPDATE tenants t
SET client_count = (
  SELECT COUNT(*) FROM xero_connections xc WHERE xc.tenant_id = t.id
);
```

---

## Unresolved Items

None - all technical decisions are resolved.

## Dependencies Identified

1. **Stripe Account**: Must be configured with products and prices
2. **Clerk Integration**: Existing auth continues to work
3. **XeroConnection Model**: Used for client count tracking
4. **Existing Tenant Model**: Extended with new fields

## Next Steps

1. Create data-model.md with entity definitions
2. Create API contracts in contracts/
3. Create quickstart.md for developer setup
