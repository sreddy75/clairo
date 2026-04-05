# Feature Specification: Stripe Billing — Beta Launch Readiness

**Feature Branch**: `043-stripe-billing`
**Created**: 2026-04-05
**Status**: Draft
**Input**: User description: "Spec 053 — Stripe Billing Integration: webhooks, billing settings, trial expiry, access restriction"

## Context: What Already Exists

The billing module is substantially built. This spec addresses the **gaps** preventing production readiness:

**Already built (backend)**: WebhookHandler (7 event types), StripeClient (full CRUD), BillingService (trial, checkout, portal, upgrade, downgrade, cancel), email templates (trial reminder, conversion, payment failed), billing event recording, usage tracking.

**Already built (frontend)**: Billing settings page (`/settings/billing`), SubscriptionCard, UsageDashboard, TrialBanner, UpgradePrompt, PricingTable, billing API client, billing history page.

**Gaps identified**: Webhook endpoint not registered with Stripe, no access restriction when subscription lapses, trial expiry UX incomplete, Stripe Customer Portal not configured, billing page not wired to real Stripe data in all flows, no end-to-end testing of payment lifecycle.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Webhook-Driven Subscription Sync (Priority: P1)

When Stripe sends a webhook event (payment succeeded, payment failed, subscription updated, trial ending), the system automatically updates the tenant's subscription status and sends appropriate email notifications without any manual intervention.

**Why this priority**: Without working webhooks, the system can't react to real payment events. Everything downstream (access restriction, trial expiry, dunning) depends on this.

**Independent Test**: Register the webhook endpoint with Stripe, trigger test events from the Stripe dashboard, and verify the tenant's subscription status updates correctly in the database.

**Acceptance Scenarios**:

1. **Given** a tenant on a trial subscription, **When** Stripe sends a `customer.subscription.trial_will_end` event 3 days before trial end, **Then** the system sends a trial reminder email to the tenant owner
2. **Given** a tenant on a trial subscription, **When** Stripe sends a `customer.subscription.updated` event with status `paused` (trial ended, no payment method), **Then** the tenant's subscription_status changes to SUSPENDED
3. **Given** a tenant with status PAST_DUE, **When** Stripe sends an `invoice.paid` event, **Then** the tenant's status changes to ACTIVE and a confirmation email is sent
4. **Given** a tenant with an active subscription, **When** Stripe sends an `invoice.payment_failed` event, **Then** the tenant's status changes to PAST_DUE and a payment failed email is sent with a 7-day grace period notice
5. **Given** a webhook event that has already been processed (duplicate delivery), **When** the same event arrives again, **Then** the system returns success without reprocessing (idempotent)

---

### User Story 2 — Access Restriction for Lapsed Subscriptions (Priority: P1)

When a tenant's subscription is suspended, cancelled, or past due beyond the grace period, the system restricts access to a read-only mode and displays a clear call-to-action to resolve the billing issue. The accountant can still view their data but cannot create, modify, or sync data.

**Why this priority**: Without access restriction, there is no enforcement of the subscription. Users could use the platform indefinitely after trial ends.

**Independent Test**: Set a tenant's subscription_status to SUSPENDED and verify the UI shows a billing resolution prompt on every page, write operations are blocked, and the user can navigate to billing settings to resolve.

**Acceptance Scenarios**:

1. **Given** a tenant with SUSPENDED status, **When** the accountant navigates to any page, **Then** a persistent banner appears stating the subscription needs attention, with a "Resolve" button linking to billing settings
2. **Given** a tenant with SUSPENDED status, **When** the accountant tries to sync Xero data, create a BAS session, or run AI analysis, **Then** the operation is blocked with a message directing them to update their payment method
3. **Given** a tenant with PAST_DUE status within the 7-day grace period, **When** the accountant uses the platform, **Then** a warning banner shows with days remaining in grace period, but all features remain functional
4. **Given** a tenant with CANCELLED status, **When** the accountant navigates to the platform, **Then** they see a "Your subscription has ended" page with options to resubscribe or export their data
5. **Given** a tenant with ACTIVE or TRIAL status, **When** the accountant uses the platform, **Then** no billing restrictions are applied

---

### User Story 3 — Payment Method Collection Before Trial Ends (Priority: P2)

As a trial user approaching the end of their 14-day trial, the accountant sees increasingly prominent prompts to add a payment method. They can add their payment details via Stripe Customer Portal without leaving the Clairo experience, ensuring seamless conversion from trial to paid.

**Why this priority**: This directly impacts revenue conversion. Without a smooth payment method collection flow, trial users churn at the end of the trial period.

**Independent Test**: Create a trial tenant with 3 days remaining, verify the upgrade prompt appears, click through to Stripe Customer Portal, add a test card, and verify the subscription continues after trial ends.

**Acceptance Scenarios**:

1. **Given** a trial with 7+ days remaining, **When** the accountant views the dashboard, **Then** a subtle trial banner shows days remaining (already implemented)
2. **Given** a trial with 3 days remaining, **When** the accountant views any page, **Then** a more prominent trial ending banner appears with an "Add Payment Method" button
3. **Given** a trial user clicking "Add Payment Method", **When** they are redirected to Stripe Customer Portal, **Then** they can enter their card details and are returned to Clairo's billing page
4. **Given** a trial user who has added a payment method, **When** the trial period ends, **Then** the subscription transitions to active billing automatically and a welcome-to-paid email is sent
5. **Given** a trial user who has NOT added a payment method, **When** the trial period ends, **Then** the subscription is paused and the user is shown the access restriction (User Story 2)

---

### User Story 4 — Billing Settings Self-Service (Priority: P2)

The accountant can view their current subscription details, billing history, and manage their subscription through a billing settings page. They can update payment methods, view invoices, and cancel their subscription — all through Stripe Customer Portal integration.

**Why this priority**: Self-service billing reduces support burden and gives accountants control over their subscription.

**Independent Test**: Navigate to `/settings/billing`, verify current plan and status are displayed, click "Manage Billing" to open Stripe Customer Portal, and verify return flow works correctly.

**Acceptance Scenarios**:

1. **Given** an active subscriber, **When** they visit billing settings, **Then** they see their current plan ($299/month Starter), subscription status, next billing date, and usage summary
2. **Given** an active subscriber, **When** they click "Manage Billing", **Then** Stripe Customer Portal opens where they can update payment method, view invoices, and manage subscription
3. **Given** a subscriber who cancels via Stripe Customer Portal, **When** they return to Clairo, **Then** the billing page shows "Cancels on [date]" with access until end of current period
4. **Given** a subscriber viewing billing history, **When** they visit the billing history page, **Then** they see a list of past billing events (payments, failures, refunds) with dates and amounts

---

### User Story 5 — Dunning: Failed Payment Recovery (Priority: P3)

When a payment fails (expired card, insufficient funds), the system enters a 7-day grace period during which the accountant retains full access but sees prominent warnings. After the grace period, access is restricted until payment is resolved.

**Why this priority**: Involuntary churn from failed payments can be recovered. A grace period with clear communication gives users time to fix their payment method.

**Independent Test**: Simulate a payment failure via Stripe test cards, verify the grace period banner appears, wait for grace period to expire, verify access restriction activates.

**Acceptance Scenarios**:

1. **Given** a payment failure occurs, **When** the accountant next visits the platform, **Then** a warning banner displays "Payment failed — update your payment method within 7 days to avoid service interruption" with an "Update Payment" button
2. **Given** a payment failure within the grace period, **When** the accountant updates their payment method and the retry succeeds, **Then** the warning banner disappears and status returns to ACTIVE
3. **Given** a payment failure where the 7-day grace period has expired, **When** the accountant visits the platform, **Then** access is restricted (same as SUSPENDED in User Story 2)

---

### Edge Cases

- What happens if a webhook arrives before the tenant record is created? The handler logs a warning and returns success (already implemented).
- What happens if the Stripe API is unreachable when the user clicks "Manage Billing"? Display a user-friendly error with a retry option.
- What happens if a user has multiple browser tabs open when subscription lapses? All tabs should show the restriction banner on next navigation or API call.
- What happens during Stripe downtime? The system continues to serve based on the last known subscription status. Webhook events are retried by Stripe.
- What if the same user creates multiple Stripe customers? The system uses `stripe_customer_id` on the Tenant model — one customer per tenant.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST process Stripe webhook events and update tenant subscription status within 30 seconds of event delivery
- **FR-002**: System MUST handle webhook events idempotently — duplicate events must not cause duplicate processing or duplicate emails
- **FR-003**: System MUST verify Stripe webhook signatures before processing any event
- **FR-004**: System MUST restrict write operations (Xero sync, BAS creation, AI analysis) when tenant subscription status is SUSPENDED or CANCELLED
- **FR-005**: System MUST display a persistent, non-dismissible banner when subscription requires attention (PAST_DUE, SUSPENDED, CANCELLED)
- **FR-006**: System MUST allow accountants to add a payment method via Stripe Customer Portal before or after trial ends
- **FR-007**: System MUST send email notifications for: trial ending (3 days before), trial converted (first payment), payment failed, subscription cancelled
- **FR-008**: System MUST maintain a 7-day grace period after payment failure before restricting access
- **FR-009**: System MUST display the billing settings page with current plan, status, next billing date, and a link to Stripe Customer Portal
- **FR-010**: System MUST allow data export even when subscription is SUSPENDED or CANCELLED (read-only access preserved)
- **FR-011**: System MUST register the webhook endpoint with Stripe and configure the required event types
- **FR-012**: System MUST display the correct price ($299/month AUD) in all billing UI

### Key Entities

- **Tenant**: Extended with subscription lifecycle fields — `subscription_status` (TRIAL, ACTIVE, PAST_DUE, SUSPENDED, CANCELLED), `stripe_customer_id`, `stripe_subscription_id`, `current_period_end`, `tier`
- **BillingEvent**: Records each Stripe webhook event with: `stripe_event_id`, `event_type`, `event_data`, `amount_cents`, `tenant_id`. Used for billing history and idempotency checks
- **Subscription Status State Machine**: TRIAL → ACTIVE (payment method added + trial ends), TRIAL → SUSPENDED (no payment method + trial ends), ACTIVE → PAST_DUE (payment fails), PAST_DUE → ACTIVE (payment succeeds), PAST_DUE → SUSPENDED (grace period expires), ANY → CANCELLED (user cancels)

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Data Modification Events**: Subscription status changes, payment events, cancellation
- [x] **Integration Events**: Stripe webhook processing, Customer Portal sessions

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| billing.subscription.status_changed | Webhook updates status | old_status, new_status, stripe_event_id | 7 years | None |
| billing.payment.succeeded | invoice.paid webhook | amount, currency, invoice_id | 7 years | None |
| billing.payment.failed | invoice.payment_failed webhook | amount, failure_reason | 7 years | None |
| billing.subscription.cancelled | User cancels | cancel_reason, effective_date | 7 years | None |
| billing.portal.accessed | User opens Stripe Portal | user_id, session_id | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Billing data retention for 7 years (standard business record keeping). Payment records may be needed for GST BAS lodgement if Clairo charges GST.
- **Data Retention**: BillingEvent records retained for 7 years minimum
- **Access Logging**: Billing events visible to tenant admins only. Stripe portal access logged.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Webhook events are processed and tenant status updated within 30 seconds of Stripe delivery
- **SC-002**: 100% of trial expirations without payment method result in SUSPENDED status within 1 hour
- **SC-003**: Accountants can add a payment method and resolve billing issues in under 2 minutes via Stripe Customer Portal
- **SC-004**: All subscription status changes trigger appropriate email notifications with zero missed events
- **SC-005**: Suspended/cancelled tenants cannot perform write operations (Xero sync, BAS creation, AI analysis)
- **SC-006**: The billing settings page loads and displays accurate subscription data within 3 seconds
- **SC-007**: Payment recovery during the 7-day grace period restores full access automatically
