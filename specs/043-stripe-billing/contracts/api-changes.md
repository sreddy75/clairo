# API Contract Changes: Stripe Billing

**Date**: 2026-04-05

## Changes to Existing Endpoints

### 1. GET /api/v1/auth/bootstrap — Add subscription fields

**Current response** (partial):
```json
{
  "user": { ... },
  "features": { ... },
  "trial_status": { ... },
  "tos_accepted_at": "2026-04-05T12:00:00Z",
  "tos_version_accepted": "1.0"
}
```

**Updated response** (2 new fields):
```json
{
  "user": { ... },
  "features": { ... },
  "trial_status": { ... },
  "tos_accepted_at": "2026-04-05T12:00:00Z",
  "tos_version_accepted": "1.0",
  "subscription_status": "trial",
  "can_access": true
}
```

| Field | Type | Values | Description |
|-------|------|--------|-------------|
| `subscription_status` | string | trial, active, past_due, suspended, cancelled, grandfathered | Current subscription state |
| `can_access` | boolean | true/false | Whether write operations are allowed |

### 2. Write endpoints — Add 403 response

All write endpoints gain a new 403 response when subscription is SUSPENDED or CANCELLED:

**Affected endpoints** (non-exhaustive):
- POST /api/v1/integrations/xero/sync
- POST /api/v1/clients/{id}/bas/sessions
- POST /api/v1/tax-plans
- POST /api/v1/queries (AI assistant)
- POST /api/v1/clients/{id}/bas/sessions/{id}/classification/request

**403 Response**:
```json
{
  "error": {
    "code": "SUBSCRIPTION_REQUIRED",
    "message": "Your subscription is inactive. Please update your billing to continue.",
    "details": {
      "subscription_status": "suspended",
      "billing_url": "/settings/billing"
    }
  }
}
```

## No New Endpoints Required

All necessary endpoints already exist in the billing router:
- GET /api/v1/billing/subscription
- POST /api/v1/billing/subscription/portal (→ Stripe Customer Portal)
- POST /api/v1/billing/subscription/checkout (→ Stripe Checkout)
- POST /api/v1/billing/subscription/cancel
- GET /api/v1/billing/billing/events
- POST /api/v1/billing/webhooks/stripe
