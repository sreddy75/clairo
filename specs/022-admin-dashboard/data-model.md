# Data Model: Admin Dashboard (Internal)

**Feature Branch**: `feature/022-admin-dashboard`
**Created**: 2026-01-01
**Phase**: 1 (Design)

## Entity Overview

```
┌─────────────────┐     ┌─────────────────────────┐
│     Tenant      │────<│   FeatureFlagOverride   │
│   (existing)    │     │        (new)            │
└────────┬────────┘     └─────────────────────────┘
         │
         │1:N
         ▼
┌─────────────────┐
│  BillingEvent   │
│  (extended)     │
└─────────────────┘
```

## New Entities

### FeatureFlagOverride

Per-tenant override for feature flags, allowing admins to enable/disable features outside tier defaults.

```python
class FeatureFlagOverride(Base):
    """Per-tenant feature flag override.

    Allows admins to override tier-based feature flags for specific tenants.
    When an override exists, it takes precedence over the tier default.
    """
    __tablename__ = "feature_flag_overrides"

    id: UUID                    # Primary key
    tenant_id: UUID             # FK to tenants.id (required)
    feature_key: str            # Feature name (max 50 chars)
    override_value: bool | None # True=enabled, False=disabled, None=use tier default
    reason: str                 # Required audit reason (max 500 chars)
    created_by: UUID            # FK to practice_users.id (admin who created)
    created_at: datetime        # Creation timestamp
    updated_at: datetime        # Last update timestamp
    updated_by: UUID | None     # FK to practice_users.id (admin who last updated)

    # Constraints
    - UNIQUE(tenant_id, feature_key)
    - CHECK(feature_key IN ('ai_insights', 'client_portal', 'custom_triggers',
                            'api_access', 'knowledge_base', 'magic_zone'))
```

**Indexes**:
- `ix_feature_flag_overrides_tenant_id` on (tenant_id)
- `ix_feature_flag_overrides_feature_key` on (feature_key)

**Relationships**:
- `tenant`: Many-to-one with Tenant
- `creator`: Many-to-one with PracticeUser (created_by)
- `updater`: Many-to-one with PracticeUser (updated_by)

### AdminAuditEvent (Extended from BillingEvent)

The existing `BillingEvent` model will be extended with new event types for admin actions.

**New Event Types**:
| event_type | Description | event_data Fields |
|------------|-------------|-------------------|
| `admin.tier_changed` | Subscription tier change | old_tier, new_tier, reason |
| `admin.credit_applied` | Credit applied to account | amount_cents, credit_type, reason |
| `admin.flag_overridden` | Feature flag override | feature_key, old_value, new_value, reason |
| `admin.tenant_viewed` | Admin viewed tenant details | (none - minimal audit) |

**Example event_data**:
```json
{
  "event_type": "admin.tier_changed",
  "event_data": {
    "old_tier": "starter",
    "new_tier": "professional",
    "reason": "Customer requested upgrade for trial period",
    "operator_id": "uuid",
    "stripe_subscription_id": "sub_xxx"
  }
}
```

## Extended Entities

### Tenant (Modifications)

No schema changes required. The Tenant model already has all fields needed:
- `tier`: SubscriptionTier enum
- `client_count`: int
- `stripe_customer_id`: str
- `stripe_subscription_id`: str
- `is_active`: bool
- `owner_email`: str

**New Computed Fields** (via service layer):
- `feature_flags`: dict - Merged tier defaults + overrides
- `mrr_contribution`: Decimal - Revenue contribution

## Validation Rules

### FeatureFlagOverride

| Field | Validation |
|-------|------------|
| tenant_id | Must exist in tenants table, tenant must be active |
| feature_key | Must be valid feature name from FeatureName type |
| override_value | True, False, or None only |
| reason | Required, 10-500 characters |
| created_by | Must be admin or super_admin role |

### Tier Change

| Rule | Validation |
|------|------------|
| Downgrade with excess clients | Warning required, confirmation flag |
| Enterprise downgrade | Blocked without super_admin |
| Same tier change | Blocked - no-op |
| Self-modification | Blocked - cannot modify own tenant |

### Credit Application

| Rule | Validation |
|------|------------|
| Amount | Positive integer (cents), max 100000 (AU$1000) |
| Reason | Required, 10-500 characters |
| Credit type | "one_time" or "recurring" |

## State Transitions

### Feature Flag Override Lifecycle

```
[No Override]
     │
     │ Create override
     ▼
[Override Active]
     │
     ├── Update value → [Override Active]
     │
     └── Delete/Set to null → [No Override]
```

### Tier Change Flow

```
[Current Tier]
     │
     │ Admin initiates change
     ▼
[Pending Stripe]
     │
     ├── Stripe success → [New Tier] + BillingEvent recorded
     │
     └── Stripe failure → [Current Tier] + Error logged, retry queued
```

## Migration Requirements

### New Table: feature_flag_overrides

```sql
CREATE TABLE feature_flag_overrides (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    tenant_id UUID NOT NULL REFERENCES tenants(id) ON DELETE CASCADE,
    feature_key VARCHAR(50) NOT NULL,
    override_value BOOLEAN,
    reason VARCHAR(500) NOT NULL,
    created_by UUID NOT NULL REFERENCES practice_users(id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_by UUID REFERENCES practice_users(id),
    CONSTRAINT uq_feature_flag_override UNIQUE (tenant_id, feature_key),
    CONSTRAINT ck_feature_key CHECK (
        feature_key IN ('ai_insights', 'client_portal', 'custom_triggers',
                        'api_access', 'knowledge_base', 'magic_zone')
    )
);

CREATE INDEX ix_feature_flag_overrides_tenant_id ON feature_flag_overrides(tenant_id);
CREATE INDEX ix_feature_flag_overrides_feature_key ON feature_flag_overrides(feature_key);
```

### BillingEvent Updates

No schema changes needed - existing `event_type` and `event_data` fields accommodate admin events.

## Query Patterns

### Get Tenant with Feature Flags

```python
# 1. Get tenant
tenant = await tenant_repo.get(tenant_id)

# 2. Get tier defaults
tier_features = get_tier_features(tenant.tier.value)

# 3. Get overrides
overrides = await override_repo.get_by_tenant(tenant_id)

# 4. Merge (overrides win)
for override in overrides:
    if override.override_value is not None:
        tier_features[override.feature_key] = override.override_value
```

### Calculate MRR

```python
# Query Stripe for active subscriptions
subscriptions = await stripe_client.list_subscriptions(status="active")

# Sum monthly values (normalize annual to monthly)
mrr = sum(
    sub.items.data[0].price.unit_amount / (12 if sub.items.data[0].price.interval == "year" else 1)
    for sub in subscriptions
)
```

### Get Revenue Metrics

```python
# Calculate for date range
start_mrr = await get_mrr_at_date(start_date)
end_mrr = await get_mrr_at_date(end_date)

# Churn = Lost MRR / Start MRR
churned = await get_churned_mrr(start_date, end_date)
churn_rate = churned / start_mrr if start_mrr > 0 else 0

# Expansion = Upgrades - Downgrades
expansion = await get_expansion_mrr(start_date, end_date)
```
