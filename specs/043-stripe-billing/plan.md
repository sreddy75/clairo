# Implementation Plan: Stripe Billing — Beta Launch Readiness

**Branch**: `043-stripe-billing` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/043-stripe-billing/spec.md`

## Summary

Wire existing billing backend (webhooks, Stripe client, subscription management) to a working end-to-end payment lifecycle. The backend is 90% built; the gaps are: (1) bootstrap response doesn't include subscription_status so the frontend can't gate access, (2) no access restriction UI for lapsed subscriptions, (3) trial banner lacks "Add Payment Method" CTA, (4) webhook endpoint needs Stripe registration, (5) SubscriptionCard doesn't handle SUSPENDED status.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, stripe SDK, React 18 + shadcn/ui, Clerk (auth)
**Storage**: PostgreSQL 16 (no schema changes — all models exist)
**Testing**: pytest + pytest-asyncio (backend), TypeScript type-check (frontend)
**Target Platform**: Web application (Docker Compose local, Vercel + AWS prod)
**Performance Goals**: Webhook processing <30s, billing page load <3s
**Constraints**: Single tier ($299/month), AUD currency, no upgrade/downgrade flows for beta
**Scale/Scope**: ~10 beta tenants initially

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | billing module follows standard pattern |
| Repository pattern | PASS | BillingEventRepository exists |
| Multi-tenancy (tenant_id) | PASS | All billing queries scoped by tenant_id |
| Audit logging | PASS | BillingEvent records all webhook events |
| Domain exceptions | PASS | billing/exceptions.py has SubscriptionError, FeatureNotAvailableError |
| Type hints everywhere | PASS | All existing billing code is typed |
| No cross-module DB queries | PASS | Billing calls auth models via service layer |

## Project Structure

### Documentation (this feature)

```text
specs/043-stripe-billing/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api-changes.md   # Endpoint changes needed
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

### Source Code (changes needed)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── auth/
│   │   │   └── router.py              # Add subscription_status to bootstrap response
│   │   ├── billing/
│   │   │   ├── router.py              # Fix webhook_secret access, add subscription guard dependency
│   │   │   ├── service.py             # Add subscription status check helper
│   │   │   ├── webhooks.py            # Add audit logging to webhook handlers
│   │   │   └── middleware.py          # NEW: subscription guard middleware/dependency
│   │   └── notifications/
│   │       └── templates.py           # Verify email templates work with real data
│   └── config.py                      # Verify STRIPE_WEBHOOK_SECRET env var
├── .env                               # Add STRIPE_WEBHOOK_SECRET
└── tests/
    └── unit/modules/billing/
        ├── test_webhooks.py           # Test webhook handlers with mock Stripe events
        └── test_subscription_guard.py # Test access restriction logic

frontend/
├── src/
│   ├── app/(protected)/
│   │   ├── layout.tsx                 # Add subscription status gating + banners
│   │   ├── subscription-expired/
│   │   │   └── page.tsx               # NEW: expired subscription landing page
│   │   └── settings/billing/
│   │       └── page.tsx               # Wire "Manage Billing" for all states
│   ├── components/billing/
│   │   ├── TrialBanner.tsx            # Add "Add Payment Method" button
│   │   ├── SubscriptionCard.tsx       # Handle SUSPENDED status
│   │   ├── SubscriptionBanner.tsx     # NEW: persistent banner for PAST_DUE/SUSPENDED
│   │   └── PaymentFailedBanner.tsx    # NEW: grace period warning banner
│   └── types/billing.ts              # Add subscription_status type
```

## Implementation Phases

### Phase 1: Bootstrap + Access Gating (P1 — US1 + US2)

**Goal**: Frontend knows subscription status and can restrict access.

**Backend changes**:
1. Add `subscription_status` and `can_access` to bootstrap response (`auth/router.py:314`)
2. Create `require_active_subscription` FastAPI dependency (`billing/middleware.py`) that raises 403 for SUSPENDED/CANCELLED tenants on write endpoints
3. Apply the guard to write endpoints: Xero sync, BAS session creation, AI analysis, classification requests

**Frontend changes**:
1. Consume `subscription_status` in protected layout bootstrap (`layout.tsx:254`)
2. Add status-based routing:
   - SUSPENDED/CANCELLED → show `SubscriptionBanner` (persistent, non-dismissible) + block navigation to write flows
   - PAST_DUE → show `PaymentFailedBanner` with grace period countdown, allow full access
   - CANCELLED → redirect to `/subscription-expired` page
3. Create `SubscriptionBanner` component (coral bg, "Your subscription needs attention" + "Resolve" button)
4. Create `/subscription-expired` page (options: resubscribe or export data)

### Phase 2: Trial Conversion Flow (P2 — US3)

**Goal**: Trial users can add payment method before trial ends.

**Changes**:
1. Update `TrialBanner` to show "Add Payment Method" button (calls `openBillingPortal()`) when ≤3 days remaining
2. Update `SubscriptionCard` to show Stripe Customer Portal button for trial users (currently hidden)
3. Configure Stripe Customer Portal in Stripe dashboard (payment method collection, no cancel for trial)
4. Verify `trial_will_end` webhook sends reminder email with correct template

### Phase 3: Billing Settings Polish (P2 — US4)

**Goal**: Billing settings page works end-to-end with real Stripe data.

**Changes**:
1. Update `SubscriptionCard` to handle all 6 statuses (add SUSPENDED case)
2. Verify "Manage Billing" → Stripe Portal → return flow works
3. Verify billing history page shows real BillingEvent data
4. Fix price display to show $299 AUD consistently

### Phase 4: Webhook Registration + E2E Testing (P1 — US1)

**Goal**: Webhooks work in the Stripe sandbox.

**Changes**:
1. Register webhook endpoint with Stripe CLI or dashboard
2. Add `STRIPE_WEBHOOK_SECRET` to `.env`
3. Test all 7 webhook handlers with Stripe CLI `stripe trigger` commands
4. Add audit logging to webhook handlers (status change events)
5. Verify idempotency (send same event twice)

### Phase 5: Dunning / Grace Period (P3 — US5)

**Goal**: Failed payments handled gracefully with 7-day grace.

**Changes**:
1. Verify `invoice.payment_failed` handler sets PAST_DUE correctly
2. `PaymentFailedBanner` shows grace period countdown (days remaining = `current_period_end - now + 7`)
3. After 7 days past_due, Stripe pauses subscription → `subscription.updated` webhook → SUSPENDED status
4. Configure Stripe retry schedule (3 attempts over 7 days) in Stripe dashboard

## Complexity Tracking

No constitution violations. All changes fit within existing module boundaries.
