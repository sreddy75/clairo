# Research: Stripe Billing — Beta Launch Readiness

**Date**: 2026-04-05

## R1: Existing Code Coverage

**Decision**: The backend billing module is 90% built. Focus implementation on wiring, not building.

**Rationale**: After code analysis, the following already exist and work:
- `WebhookHandler` with 7 event type handlers (webhooks.py:20-525)
- `StripeClient` with full CRUD (stripe_client.py:27-330)
- `BillingService` with trial/checkout/portal/upgrade/downgrade/cancel (service.py:40-310)
- Email templates for trial reminder, conversion, payment failed (templates.py)
- `BillingEventRepository` with idempotency checks (repository.py)
- Billing router with 15 endpoints (router.py)
- Frontend billing API client with 17 functions (billing.ts)
- SubscriptionCard, TrialBanner, UsageDashboard components
- Billing settings page with modals for upgrade/downgrade

**What's missing (5 specific gaps)**:
1. Bootstrap response lacks `subscription_status` → frontend can't gate access
2. No `require_active_subscription` dependency for write endpoints
3. TrialBanner lacks "Add Payment Method" CTA
4. SubscriptionCard doesn't handle SUSPENDED status
5. No SubscriptionBanner/PaymentFailedBanner components

## R2: Stripe Customer Portal Configuration

**Decision**: Use Stripe Customer Portal for all payment method management.

**Rationale**: Stripe Customer Portal is a hosted page that handles:
- Adding/updating payment methods
- Viewing invoices and receipts
- Cancelling subscriptions
- No PCI compliance burden on Clairo

**Configuration needed** (in Stripe dashboard):
- Enable "Payment methods" section
- Enable "Invoice history" section
- Set "Cancel subscription" to "at end of period"
- Set return URL to `{frontend_url}/settings/billing`
- For trial users: enable payment method collection without full portal

**Alternatives considered**:
- Stripe Checkout for payment collection → More complex redirect flow, better for initial subscription but portal is simpler for updates
- Custom payment form with Stripe Elements → PCI compliance overhead, not worth it for beta

## R3: Access Restriction Strategy

**Decision**: Two-layer gating — backend dependency (403 on write endpoints) + frontend UI restriction (banners + redirects).

**Rationale**: Backend gating alone would show confusing API errors. Frontend gating alone could be bypassed. Both layers together provide defense-in-depth.

**Backend approach**: FastAPI dependency `require_active_subscription` that:
- Reads tenant from the existing `get_current_tenant` dependency
- Checks `tenant.can_access` property (already defined in auth/models.py:396)
- Raises 403 `SubscriptionRequiredError` for SUSPENDED/CANCELLED
- Applied to write endpoints only (sync, create, AI analysis)
- NOT applied to read endpoints (view data, export, billing settings)

**Frontend approach**: Protected layout checks `subscription_status` from bootstrap:
- ACTIVE/TRIAL/GRANDFATHERED → normal access
- PAST_DUE → show warning banner, full access continues
- SUSPENDED → show persistent banner, hide write action buttons
- CANCELLED → redirect to `/subscription-expired` page

## R4: Webhook Registration

**Decision**: Register via Stripe CLI for development, Stripe dashboard for production.

**Rationale**: Stripe CLI (`stripe listen --forward-to`) is ideal for local development — creates a temporary webhook endpoint that forwards events to localhost. For production, register the endpoint URL in the Stripe dashboard.

**Events to register**:
- `customer.subscription.created`
- `customer.subscription.updated`
- `customer.subscription.deleted`
- `customer.subscription.trial_will_end`
- `checkout.session.completed`
- `invoice.paid`
- `invoice.payment_failed`

**Local development flow**:
1. `stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe`
2. Copy the webhook signing secret to `STRIPE_WEBHOOK_SECRET` in `.env`
3. Trigger test events: `stripe trigger invoice.payment_failed`

## R5: Grace Period Implementation

**Decision**: 7-day grace period managed by Stripe's retry schedule, not custom logic.

**Rationale**: Stripe has built-in retry logic for failed payments. Configure Stripe to retry 3 times over 7 days. After all retries fail, Stripe sends `customer.subscription.updated` with `status: paused` (or `past_due` depending on config). This avoids building a custom timer/cron job.

**Stripe dashboard configuration**:
- Settings → Billing → Subscriptions → Manage failed payments
- Retry schedule: 3 attempts (day 1, day 3, day 7)
- After all retries fail: "Pause the subscription"
- This triggers `subscription.updated` with status `paused` → our handler maps to SUSPENDED

## R6: Bootstrap Response Extension

**Decision**: Add `subscription_status` and `can_access` boolean to existing bootstrap response.

**Rationale**: The bootstrap endpoint (`auth/router.py:314`) already returns `features` and `trial_status`. Adding 2 fields is minimal change. The frontend layout already consumes bootstrap data, so adding status gating is straightforward.

**Schema change**:
```python
# Add to BootstrapResponse
subscription_status: str  # "trial", "active", "past_due", "suspended", "cancelled"
can_access: bool  # True if tenant can use write features
```

No database changes needed. All fields derive from existing `Tenant` model columns.
