# Data Model: Stripe Billing — Beta Launch Readiness

**Date**: 2026-04-05

## No Schema Changes Required

All necessary database entities already exist. This spec requires zero migrations.

## Existing Entities (reference)

### Tenant (auth/models.py)

Already has all billing fields:

| Field | Type | Purpose |
|-------|------|---------|
| `stripe_customer_id` | VARCHAR | Stripe customer reference |
| `stripe_subscription_id` | VARCHAR | Stripe subscription reference |
| `tier` | ENUM(starter, professional, growth, enterprise) | Subscription tier |
| `subscription_status` | ENUM(trial, active, past_due, suspended, cancelled, grandfathered) | Current billing state |
| `current_period_end` | TIMESTAMPTZ | When current billing period ends |
| `client_count` | INTEGER | Number of active clients |

**Computed property** (`can_access`): Returns `True` for TRIAL, ACTIVE, PAST_DUE, GRANDFATHERED. Returns `False` for SUSPENDED, CANCELLED.

### BillingEvent (billing/models.py)

Already exists for webhook event recording:

| Field | Type | Purpose |
|-------|------|---------|
| `id` | UUID | Primary key |
| `tenant_id` | UUID FK | Tenant reference |
| `stripe_event_id` | VARCHAR UNIQUE | Stripe event ID (idempotency) |
| `event_type` | VARCHAR | e.g. "invoice.paid" |
| `event_data` | JSONB | Full event payload |
| `amount_cents` | INTEGER | Transaction amount |
| `created_at` | TIMESTAMPTZ | When processed |

### UsageSnapshot (billing/models.py)

Already exists for usage tracking.

## State Machine: Subscription Status

```
                    ┌──────────────────────┐
                    │       TRIAL          │
                    │  (14-day free trial) │
                    └──────┬───────┬───────┘
                           │       │
              payment method added  no payment method
              + trial ends         + trial ends
                           │       │
                    ┌──────▼──┐  ┌─▼──────────┐
                    │  ACTIVE │  │ SUSPENDED   │
                    │  (paid) │  │ (no access) │
                    └──┬───┬──┘  └─────────────┘
                       │   │           ▲
              payment  │   │ payment   │ grace period
              succeeds │   │ fails     │ expires (7d)
                       │   │           │
                    ┌──▼───▼──┐        │
                    │ PAST_DUE├────────┘
                    │ (grace) │
                    └─────────┘

           ANY ──── user cancels ────► CANCELLED
```

## API Response Schema Changes

### BootstrapResponse (add 2 fields)

```
existing fields:
  user, features, trial_status, tos_accepted_at, tos_version_accepted

new fields:
  subscription_status: string  // "trial" | "active" | "past_due" | "suspended" | "cancelled" | "grandfathered"
  can_access: boolean          // true if write operations allowed
```
