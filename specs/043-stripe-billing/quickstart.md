# Quickstart: Stripe Billing Implementation

**Date**: 2026-04-05

## Prerequisites

- Stripe sandbox account configured (done — `sk_test_*` key in `.env`)
- Stripe product + price created (done — `price_1TIpl4IfvXuOvBdwARHHsmjJ` at $299 AUD/month)
- Stripe CLI installed: `brew install stripe/stripe-cli/stripe`

## Local Development Setup

### 1. Stripe CLI Webhook Forwarding

```bash
# Login to Stripe CLI
stripe login

# Forward webhooks to local backend
stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe

# Copy the webhook signing secret (whsec_...) and add to .env:
# STRIPE_WEBHOOK_SECRET=whsec_...
```

### 2. Test Webhook Events

```bash
# Trigger test events
stripe trigger customer.subscription.created
stripe trigger invoice.paid
stripe trigger invoice.payment_failed
stripe trigger customer.subscription.trial_will_end
stripe trigger customer.subscription.updated
stripe trigger customer.subscription.deleted
```

### 3. Test Cards

| Card Number | Scenario |
|-------------|----------|
| 4242 4242 4242 4242 | Success |
| 4000 0000 0000 0341 | Decline (card_declined) |
| 4000 0000 0000 9995 | Decline (insufficient_funds) |
| 4000 0025 0000 3155 | Requires 3D Secure |

### 4. Stripe Customer Portal

Configure in Stripe dashboard at https://dashboard.stripe.com/test/settings/billing/portal:
- Enable "Payment methods" section
- Enable "Invoice history" section
- Enable "Cancel subscription" → "At end of billing period"
- Return URL: `http://localhost:3000/settings/billing`

## Key Files to Modify

### Backend (in order of implementation)

1. `backend/app/modules/auth/router.py` — Add `subscription_status` + `can_access` to bootstrap response
2. `backend/app/modules/billing/middleware.py` — NEW: `require_active_subscription` dependency
3. `backend/app/modules/billing/router.py` — Apply subscription guard to write endpoints
4. `backend/.env` — Add `STRIPE_WEBHOOK_SECRET`

### Frontend (in order of implementation)

1. `frontend/src/app/(protected)/layout.tsx` — Consume subscription_status, add gating logic
2. `frontend/src/components/billing/SubscriptionBanner.tsx` — NEW: persistent banner for lapsed subscriptions
3. `frontend/src/components/billing/TrialBanner.tsx` — Add "Add Payment Method" CTA
4. `frontend/src/components/billing/SubscriptionCard.tsx` — Handle SUSPENDED status
5. `frontend/src/app/(protected)/subscription-expired/page.tsx` — NEW: expired landing page

## Verification Checklist

- [ ] `stripe listen` forwards events to local backend
- [ ] Bootstrap response includes `subscription_status` and `can_access`
- [ ] Setting tenant status to SUSPENDED shows restriction banner
- [ ] Setting tenant status to CANCELLED redirects to expired page
- [ ] TrialBanner shows "Add Payment Method" when ≤3 days remain
- [ ] "Manage Billing" opens Stripe Customer Portal
- [ ] Webhook idempotency: sending same event twice doesn't duplicate processing
- [ ] Payment failed → PAST_DUE → grace period banner shows
