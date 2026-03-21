# Data Model: Subscription & Feature Gating

**Date**: 2025-12-31
**Spec**: 019-subscription-feature-gating

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                         TENANT                                   │
│  (Extended with subscription fields)                             │
├─────────────────────────────────────────────────────────────────┤
│  id: UUID (PK)                                                   │
│  name: VARCHAR(255)                                              │
│  slug: VARCHAR(50) UNIQUE                                        │
│  settings: JSONB                                                 │
│  mfa_required: BOOLEAN                                           │
│  is_active: BOOLEAN                                              │
│  ─────────────────────────────────────────────────────────────   │
│  tier: subscription_tier ENUM                   ← NEW            │
│  subscription_status: subscription_status ENUM  ← MODIFIED       │
│  stripe_customer_id: VARCHAR(255)               ← NEW            │
│  stripe_subscription_id: VARCHAR(255)           ← NEW            │
│  current_period_end: TIMESTAMPTZ               ← NEW            │
│  client_count: INTEGER                          ← NEW            │
│  ─────────────────────────────────────────────────────────────   │
│  created_at: TIMESTAMPTZ                                         │
│  updated_at: TIMESTAMPTZ                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ 1:N
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      BILLING_EVENTS                              │
│  (New table for audit trail)                                     │
├─────────────────────────────────────────────────────────────────┤
│  id: UUID (PK)                                                   │
│  tenant_id: UUID (FK → tenants.id)                               │
│  stripe_event_id: VARCHAR(255) UNIQUE                            │
│  event_type: VARCHAR(100)                                        │
│  event_data: JSONB                                               │
│  amount_cents: INTEGER                                           │
│  currency: VARCHAR(3)                                            │
│  status: billing_event_status ENUM                               │
│  processed_at: TIMESTAMPTZ                                       │
│  created_at: TIMESTAMPTZ                                         │
└─────────────────────────────────────────────────────────────────┘
                              │
                              │ Reference
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                      STRIPE PRODUCTS                             │
│  (Configuration in Stripe Dashboard)                             │
├─────────────────────────────────────────────────────────────────┤
│  Starter:     price_starter_monthly ($99 AUD)                    │
│  Professional: price_professional_monthly ($299 AUD)             │
│  Growth:      price_growth_monthly ($599 AUD)                    │
│  Enterprise:  Custom pricing (manual)                            │
└─────────────────────────────────────────────────────────────────┘
```

## Enum Definitions

### SubscriptionTier (NEW)

```python
class SubscriptionTier(str, enum.Enum):
    """Subscription pricing tier.

    Determines feature access and client limits.
    """
    STARTER = "starter"           # $99/mo, 25 clients, basic AI
    PROFESSIONAL = "professional"  # $299/mo, 100 clients, full features
    GROWTH = "growth"              # $599/mo, 250 clients, API access
    ENTERPRISE = "enterprise"      # Custom pricing, unlimited
```

### SubscriptionStatus (MODIFIED)

```python
class SubscriptionStatus(str, enum.Enum):
    """Tenant subscription status.

    Controls tenant access and feature availability.
    """
    TRIAL = "trial"                # 14-day trial (future Spec 021)
    ACTIVE = "active"              # Paying customer
    PAST_DUE = "past_due"          # Payment failed, grace period
    CANCELLED = "cancelled"        # Subscription ended
    SUSPENDED = "suspended"        # Admin suspended
    GRANDFATHERED = "grandfathered"  # ← NEW: Existing users, no payment
```

### BillingEventStatus (NEW)

```python
class BillingEventStatus(str, enum.Enum):
    """Status of a billing event."""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"
```

### BillingEventType (NEW)

```python
class BillingEventType(str, enum.Enum):
    """Type of billing event from Stripe."""
    SUBSCRIPTION_CREATED = "subscription.created"
    SUBSCRIPTION_UPDATED = "subscription.updated"
    SUBSCRIPTION_CANCELLED = "subscription.cancelled"
    PAYMENT_SUCCEEDED = "payment.succeeded"
    PAYMENT_FAILED = "payment.failed"
    INVOICE_PAID = "invoice.paid"
    INVOICE_PAYMENT_FAILED = "invoice.payment_failed"
```

## Entity Definitions

### Tenant (Extended)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| name | VARCHAR(255) | NOT NULL | Display name |
| slug | VARCHAR(50) | UNIQUE, NOT NULL | URL-friendly identifier |
| settings | JSONB | NOT NULL, DEFAULT '{}' | Tenant configuration |
| mfa_required | BOOLEAN | NOT NULL, DEFAULT false | MFA requirement |
| is_active | BOOLEAN | NOT NULL, DEFAULT true | Platform access |
| **tier** | subscription_tier | NOT NULL, DEFAULT 'professional' | Pricing tier |
| **subscription_status** | subscription_status | NOT NULL, DEFAULT 'grandfathered' | Payment status |
| **stripe_customer_id** | VARCHAR(255) | NULLABLE, UNIQUE | Stripe customer ID |
| **stripe_subscription_id** | VARCHAR(255) | NULLABLE | Active subscription ID |
| **current_period_end** | TIMESTAMPTZ | NULLABLE | Billing period end date |
| **client_count** | INTEGER | NOT NULL, DEFAULT 0 | Denormalized client count |
| created_at | TIMESTAMPTZ | NOT NULL | Creation timestamp |
| updated_at | TIMESTAMPTZ | NOT NULL | Last update timestamp |

**Indexes**:
- `ix_tenants_tier` on (tier)
- `ix_tenants_stripe_customer_id` on (stripe_customer_id) WHERE NOT NULL

**Business Rules**:
- `tier` determines feature access via TIER_FEATURES config
- `client_count` is updated via database trigger on xero_connections
- `subscription_status` affects `can_access` property

### BillingEvent (NEW)

| Field | Type | Constraints | Description |
|-------|------|-------------|-------------|
| id | UUID | PK | Unique identifier |
| tenant_id | UUID | FK → tenants.id, NOT NULL | Tenant reference |
| stripe_event_id | VARCHAR(255) | UNIQUE, NOT NULL | Stripe event ID (idempotency) |
| event_type | VARCHAR(100) | NOT NULL | Stripe event type |
| event_data | JSONB | NOT NULL | Full event payload |
| amount_cents | INTEGER | NULLABLE | Amount in cents (if payment) |
| currency | VARCHAR(3) | DEFAULT 'aud' | Currency code |
| status | billing_event_status | NOT NULL, DEFAULT 'processed' | Processing status |
| processed_at | TIMESTAMPTZ | NULLABLE | When event was processed |
| created_at | TIMESTAMPTZ | NOT NULL | When event was received |

**Indexes**:
- `ix_billing_events_tenant_id` on (tenant_id)
- `ix_billing_events_stripe_event_id` on (stripe_event_id)
- `ix_billing_events_event_type` on (event_type)
- `ix_billing_events_created_at` on (created_at)

**Business Rules**:
- `stripe_event_id` ensures idempotent webhook processing
- All payment events must be logged for audit compliance

## Feature Flag Configuration (Static)

```python
# app/core/feature_flags.py

from typing import TypedDict, Literal

class TierFeatures(TypedDict):
    max_clients: int | None  # None = unlimited
    ai_insights: Literal["basic", "full"]
    client_portal: bool
    custom_triggers: bool
    api_access: bool
    knowledge_base: bool
    magic_zone: bool

TIER_FEATURES: dict[str, TierFeatures] = {
    "starter": {
        "max_clients": 25,
        "ai_insights": "basic",
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
        "max_clients": None,
        "ai_insights": "full",
        "client_portal": True,
        "custom_triggers": True,
        "api_access": True,
        "knowledge_base": True,
        "magic_zone": True,
    },
}

# Pricing (AUD cents)
TIER_PRICING = {
    "starter": 9900,       # $99
    "professional": 29900,  # $299
    "growth": 59900,        # $599
    "enterprise": None,     # Custom
}
```

## State Transitions

### Subscription Status Transitions

```
                    ┌──────────────┐
                    │              │
   New Signup ─────►│    TRIAL     │◄─── Future (Spec 021)
                    │              │
                    └──────┬───────┘
                           │
                           │ Subscribe
                           ▼
                    ┌──────────────┐
   Payment OK ─────►│    ACTIVE    │◄─── Grandfathered converts
                    │              │
                    └──────┬───────┘
                           │
            ┌──────────────┼──────────────┐
            │              │              │
            ▼              ▼              ▼
     ┌──────────────┐ ┌──────────────┐ ┌──────────────┐
     │   PAST_DUE   │ │  CANCELLED   │ │  SUSPENDED   │
     │ (grace 7d)   │ │ (by user)    │ │ (by admin)   │
     └──────┬───────┘ └──────────────┘ └──────────────┘
            │
            │ Payment OK
            ▼
     ┌──────────────┐
     │    ACTIVE    │
     └──────────────┘

                    ┌──────────────────┐
   Migration ──────►│  GRANDFATHERED   │──── Can convert to ACTIVE
                    │ (no payment req) │
                    └──────────────────┘
```

### Feature Access Decision Flow

```
Request to access feature
         │
         ▼
┌─────────────────────────┐
│ Get tenant.tier         │
└───────────┬─────────────┘
            │
            ▼
┌─────────────────────────┐
│ Lookup TIER_FEATURES    │
│ [tier][feature_name]    │
└───────────┬─────────────┘
            │
            ▼
    ┌───────┴───────┐
    │               │
    ▼               ▼
┌─────────┐   ┌─────────────┐
│ Allow   │   │ 403 + Upgrade│
│ Access  │   │ Prompt      │
└─────────┘   └─────────────┘
```

## Migration Strategy

### Step 1: Add New Enum Value

```sql
ALTER TYPE subscription_status ADD VALUE 'grandfathered';
ALTER TYPE subscription_status ADD VALUE 'past_due';
```

### Step 2: Create New Enum Type

```sql
CREATE TYPE subscription_tier AS ENUM ('starter', 'professional', 'growth', 'enterprise');
```

### Step 3: Add Columns to Tenant

```sql
ALTER TABLE tenants
  ADD COLUMN tier subscription_tier NOT NULL DEFAULT 'professional',
  ADD COLUMN stripe_customer_id VARCHAR(255) UNIQUE,
  ADD COLUMN stripe_subscription_id VARCHAR(255),
  ADD COLUMN current_period_end TIMESTAMPTZ,
  ADD COLUMN client_count INTEGER NOT NULL DEFAULT 0;

CREATE INDEX ix_tenants_tier ON tenants(tier);
CREATE INDEX ix_tenants_stripe_customer_id ON tenants(stripe_customer_id) WHERE stripe_customer_id IS NOT NULL;
```

### Step 4: Create BillingEvent Table

```sql
CREATE TYPE billing_event_status AS ENUM ('pending', 'processed', 'failed');

CREATE TABLE billing_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    stripe_event_id VARCHAR(255) NOT NULL UNIQUE,
    event_type VARCHAR(100) NOT NULL,
    event_data JSONB NOT NULL,
    amount_cents INTEGER,
    currency VARCHAR(3) DEFAULT 'aud',
    status billing_event_status NOT NULL DEFAULT 'processed',
    processed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX ix_billing_events_tenant_id ON billing_events(tenant_id);
CREATE INDEX ix_billing_events_event_type ON billing_events(event_type);
CREATE INDEX ix_billing_events_created_at ON billing_events(created_at);
```

### Step 5: Migrate Existing Tenants

```sql
-- Set all existing tenants to grandfathered Professional
UPDATE tenants
SET subscription_status = 'grandfathered',
    tier = 'professional'
WHERE subscription_status IN ('trial', 'active');

-- Initialize client_count from xero_connections
UPDATE tenants t
SET client_count = (
  SELECT COUNT(*) FROM xero_connections xc WHERE xc.tenant_id = t.id
);
```

### Step 6: Create Client Count Trigger

```sql
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

## Validation Rules

| Entity | Field | Rule |
|--------|-------|------|
| Tenant | tier | Must be valid SubscriptionTier enum value |
| Tenant | stripe_customer_id | If set, must start with "cus_" |
| Tenant | stripe_subscription_id | If set, must start with "sub_" |
| Tenant | client_count | Must be >= 0 |
| BillingEvent | stripe_event_id | Must start with "evt_" |
| BillingEvent | amount_cents | Must be >= 0 if set |
| BillingEvent | currency | Must be 3-character ISO code |

## Relationships Summary

| From | To | Cardinality | Description |
|------|-----|-------------|-------------|
| Tenant | BillingEvent | 1:N | Tenant has many billing events |
| Tenant | XeroConnection | 1:N | Used for client_count (existing) |
