# Quickstart: Subscription & Feature Gating

**Spec**: 019-subscription-feature-gating
**Date**: 2025-12-31

## Prerequisites

1. **Stripe Account** with test API keys
2. **Existing Clairo setup** (Docker, database, frontend)
3. **Clerk integration** working for authentication

## Environment Variables

Add to `.env`:

```bash
# Stripe Configuration
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Product/Price IDs (created in Step 1)
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_GROWTH=price_...
```

## Setup Steps

### Step 1: Create Stripe Products

In Stripe Dashboard (Test Mode):

1. **Products > Add Product**:
   - Name: "Clairo Starter"
   - Price: $99 AUD/month (recurring)
   - Note the `price_xxx` ID

2. Repeat for Professional ($299) and Growth ($599)

3. **Developers > Webhooks > Add Endpoint**:
   - URL: `https://your-domain.com/api/v1/webhooks/stripe`
   - Events:
     - `customer.subscription.created`
     - `customer.subscription.updated`
     - `customer.subscription.deleted`
     - `invoice.paid`
     - `invoice.payment_failed`
   - Note the `whsec_xxx` signing secret

### Step 2: Run Database Migration

```bash
# Generate migration
cd backend
alembic revision --autogenerate -m "019_subscription_feature_gating"

# Apply migration
alembic upgrade head
```

The migration will:
- Add `tier`, `stripe_customer_id`, `stripe_subscription_id`, `current_period_end`, `client_count` to tenants
- Create `billing_events` table
- Set existing tenants to `professional` tier with `grandfathered` status
- Create client count trigger

### Step 3: Verify Configuration

```python
# Backend health check
from app.core.feature_flags import TIER_FEATURES, get_tier_features

# Should return features for each tier
print(TIER_FEATURES["starter"])
print(TIER_FEATURES["professional"])

# Test feature check
from app.core.feature_flags import has_feature
assert has_feature("starter", "custom_triggers") == False
assert has_feature("professional", "custom_triggers") == True
```

### Step 4: Test Stripe Webhook Locally

Use Stripe CLI to forward webhooks:

```bash
# Install Stripe CLI
brew install stripe/stripe-cli/stripe

# Login
stripe login

# Forward webhooks to local server
stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe

# Note: Use the webhook signing secret from CLI output for local testing
```

### Step 5: Verify Frontend Hook

```typescript
// In any component
import { useTier } from '@/hooks/useTier';

function TestComponent() {
  const { tier, canAccess, clientLimit, clientCount } = useTier();

  console.log('Current tier:', tier);
  console.log('Can access triggers:', canAccess('custom_triggers'));
  console.log('Client usage:', `${clientCount}/${clientLimit}`);

  return <div>Tier: {tier}</div>;
}
```

## Quick Test Scenarios

### Test 1: Feature Gating (Backend)

```bash
# As a Starter tier tenant, try to access triggers
curl -X POST http://localhost:8000/api/v1/triggers \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "test"}'

# Expected: 403 with upgrade prompt
{
  "error": "feature_not_available",
  "feature": "custom_triggers",
  "required_tier": "professional",
  "current_tier": "starter"
}
```

### Test 2: Subscription Checkout

```bash
# Create checkout session
curl -X POST http://localhost:8000/api/v1/subscription/checkout \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"tier": "professional"}'

# Expected: Stripe checkout URL
{
  "checkout_url": "https://checkout.stripe.com/c/pay/...",
  "session_id": "cs_test_..."
}
```

### Test 3: Client Limit Enforcement

```sql
-- Set tenant to starter tier with 25 clients
UPDATE tenants SET tier = 'starter', client_count = 25 WHERE id = '...';

-- Try to add client via API - should fail
-- Expected: 403 with client_limit_exceeded error
```

### Test 4: Webhook Processing

```bash
# Trigger test event via Stripe CLI
stripe trigger customer.subscription.created

# Check billing_events table
SELECT * FROM billing_events ORDER BY created_at DESC LIMIT 1;
```

## Module Structure

After implementation, the structure will be:

```
backend/app/
├── core/
│   └── feature_flags.py      # TIER_FEATURES config
│
├── modules/
│   ├── auth/
│   │   ├── models.py         # Tenant extended
│   │   └── schemas.py        # TenantResponse updated
│   │
│   └── billing/              # NEW MODULE
│       ├── __init__.py
│       ├── models.py         # BillingEvent
│       ├── schemas.py        # Request/Response schemas
│       ├── repository.py     # Database access
│       ├── service.py        # Business logic
│       ├── router.py         # API endpoints
│       ├── stripe_client.py  # Stripe integration
│       └── webhooks.py       # Webhook handlers

frontend/src/
├── hooks/
│   └── useTier.ts            # Tier access hook
│
├── components/
│   └── billing/
│       ├── UpgradePrompt.tsx # Feature gate UI
│       ├── PricingTable.tsx  # Tier comparison
│       └── BillingPortal.tsx # Self-service link
│
├── lib/api/
│   └── billing.ts            # API client
│
└── types/
    └── billing.ts            # TypeScript types
```

## Common Issues

### Issue: Webhook signature verification failed

**Cause**: Wrong webhook secret or request body modified

**Fix**:
- Use raw request body for signature verification
- Ensure `STRIPE_WEBHOOK_SECRET` matches Stripe Dashboard

### Issue: Client count not updating

**Cause**: Trigger not created or not firing

**Fix**:
- Verify trigger exists: `\df update_tenant_client_count`
- Check trigger is attached: `\d xero_connections`

### Issue: Feature gate not enforcing

**Cause**: Decorator not applied or tenant not loaded

**Fix**:
- Verify `@require_feature()` decorator is on endpoint
- Check `get_current_tenant` dependency is working

## Next Steps

1. Create feature branch: `git checkout -b feature/019-subscription-feature-gating`
2. Implement backend module following `data-model.md`
3. Implement API following `contracts/subscription-api.yaml`
4. Implement frontend hooks and components
5. Run tests and verify all scenarios
6. Create PR for review
