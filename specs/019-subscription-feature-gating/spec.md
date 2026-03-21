# Feature Specification: Subscription & Feature Gating

**Feature Branch**: `019-subscription-feature-gating`
**Created**: 2025-12-31
**Status**: Draft
**Input**: Enable paid subscriptions with tier-based feature access. Implement Stripe integration for checkout/billing, feature flags per tier (starter/professional/growth/enterprise), backend gating decorators, frontend gating hooks, and client limit enforcement. All existing tenants start as "professional" tier with no disruption.

## User Scenarios & Testing *(mandatory)*

### User Story 1 - New Accountant Subscribes to Clairo (Priority: P1)

A new accounting practice signs up for Clairo and chooses a subscription tier that matches their practice size. They complete payment through a secure checkout process and immediately gain access to features appropriate for their tier.

**Why this priority**: This is the primary revenue-generating flow. Without subscription capability, the platform cannot monetize and sustain operations.

**Independent Test**: Can be fully tested by creating a new tenant account, selecting a tier, completing checkout, and verifying the tenant has correct tier-based access.

**Acceptance Scenarios**:

1. **Given** a new user has completed account registration, **When** they view the pricing page, **Then** they see all available tiers with clear feature comparisons and pricing
2. **Given** a user has selected a tier, **When** they click "Subscribe", **Then** they are directed to a secure payment checkout
3. **Given** a user completes payment successfully, **When** checkout is confirmed, **Then** their tenant is immediately updated with the selected tier and full access is granted
4. **Given** payment fails, **When** checkout is declined, **Then** the user sees a clear error message and can retry with different payment details

---

### User Story 2 - Existing Tenant Manages Subscription (Priority: P1)

An existing accountant needs to upgrade their tier to get more client capacity, downgrade to reduce costs, or update their payment method. They can do this self-service without contacting support.

**Why this priority**: Self-service subscription management reduces support burden and improves customer satisfaction. Critical for retention and expansion revenue.

**Independent Test**: Can be fully tested by logging in as an existing subscriber, accessing billing portal, and performing tier change or payment update operations.

**Acceptance Scenarios**:

1. **Given** an authenticated tenant owner, **When** they access subscription settings, **Then** they see their current tier, next billing date, and payment method
2. **Given** a tenant on Starter tier, **When** they click "Upgrade", **Then** they can select a higher tier and are charged the prorated difference immediately
3. **Given** a tenant on Professional tier, **When** they request a downgrade, **Then** they are informed the change takes effect at next billing cycle and they retain current access until then
4. **Given** a tenant with an expiring card, **When** they update payment method, **Then** the new card is saved and future charges use it

---

### User Story 3 - Feature Access is Enforced by Tier (Priority: P1)

Accountants can only access features included in their subscription tier. When they try to access a feature not in their tier, they see a clear prompt to upgrade rather than an error.

**Why this priority**: Feature gating is the core mechanism that drives tier differentiation and upsell opportunities. Without enforcement, there's no reason to subscribe to higher tiers.

**Independent Test**: Can be fully tested by logging in as a Starter tier tenant and attempting to access Professional-tier features, verifying upgrade prompts appear.

**Acceptance Scenarios**:

1. **Given** a Starter tier tenant, **When** they navigate to Custom Triggers, **Then** they see an upgrade prompt explaining this feature requires Professional tier
2. **Given** a Professional tier tenant, **When** they navigate to Custom Triggers, **Then** they have full access to create and manage triggers
3. **Given** a Starter tier tenant, **When** they view their dashboard, **Then** Professional-only features show a lock icon with upgrade call-to-action
4. **Given** any tier tenant, **When** they access API documentation, **Then** Growth tier requirement is clearly shown for API access

---

### User Story 4 - Client Limit Enforcement (Priority: P2)

Accountants cannot add more clients than their tier allows. They receive proactive warnings as they approach their limit and clear guidance on upgrading when they reach it.

**Why this priority**: Client limits are the primary tier differentiator for accounting practices. This drives natural upsell as practices grow.

**Independent Test**: Can be fully tested by creating a Starter tenant with 24 clients, adding one more (success), then attempting to add another (blocked with upgrade prompt).

**Acceptance Scenarios**:

1. **Given** a Starter tier tenant with 20 clients, **When** they view their dashboard, **Then** they see "20 of 25 clients used" usage indicator
2. **Given** a Starter tier tenant with 23 clients, **When** they view dashboard, **Then** they see a warning "Approaching client limit - 2 remaining"
3. **Given** a Starter tier tenant at 25 clients, **When** they try to add a new client, **Then** they are blocked and shown an upgrade prompt
4. **Given** a tenant upgrades from Starter to Professional, **When** upgrade completes, **Then** their client limit immediately increases to 100

---

### User Story 5 - Subscription Billing Events (Priority: P2)

Platform administrators can track subscription revenue, failed payments, and subscription lifecycle events. This data is essential for business operations and customer success.

**Why this priority**: Visibility into billing events enables proactive customer success (catching failed payments) and business reporting (MRR tracking).

**Independent Test**: Can be fully tested by triggering subscription events (creation, renewal, failure) and verifying they appear in admin billing dashboard.

**Acceptance Scenarios**:

1. **Given** a new subscription is created, **When** the payment succeeds, **Then** a billing event is recorded with tier, amount, and tenant details
2. **Given** a subscription renewal fails, **When** payment is declined, **Then** an event is recorded and the tenant receives notification
3. **Given** a subscription is cancelled, **When** cancellation is processed, **Then** an event is recorded with reason and effective date
4. **Given** an admin, **When** they view billing dashboard, **Then** they see MRR, subscription counts by tier, and recent events

---

### User Story 6 - Existing Tenants Migrated to Professional (Priority: P1)

All existing tenants (created before subscription system) are automatically assigned to Professional tier with no disruption to their current access. They are not charged until they explicitly choose a plan.

**Why this priority**: Migration must be seamless to avoid losing existing users. This is a critical go-live requirement.

**Independent Test**: Can be fully tested by running migration on test database, verifying all existing tenants have tier="professional" and subscription_status="grandfathered".

**Acceptance Scenarios**:

1. **Given** existing tenants with no tier assignment, **When** migration runs, **Then** all tenants are set to Professional tier with "grandfathered" status
2. **Given** a grandfathered tenant, **When** they log in, **Then** they have full Professional access with no payment required
3. **Given** a grandfathered tenant, **When** they view billing settings, **Then** they see "Grandfathered - No payment required" with option to switch to paid plan
4. **Given** a grandfathered tenant chooses a paid plan, **When** they complete checkout, **Then** their status changes from "grandfathered" to "active" subscriber

---

### Edge Cases

- What happens when a payment fails during subscription renewal?
  - Subscription enters "past_due" status, tenant retains access for grace period (7 days), receives email notifications at day 1, 3, and 7
- What happens when a tenant downgrades but exceeds the new tier's client limit?
  - Downgrade is allowed but tenant cannot add new clients until under limit; existing clients remain accessible
- What happens when Stripe webhook delivery fails?
  - Webhooks are processed idempotently; retry logic handles transient failures; admin alert for persistent failures
- What happens if tenant cancels then resubscribes?
  - Previous subscription history is preserved; new subscription starts fresh with no proration to old period

## Requirements *(mandatory)*

### Functional Requirements

**Subscription Management**:
- **FR-001**: System MUST provide a pricing page showing all available tiers with features and pricing
- **FR-002**: System MUST integrate with Stripe for secure payment processing
- **FR-003**: System MUST create a Stripe customer record when a tenant first subscribes
- **FR-004**: System MUST support monthly billing cycle for all tiers
- **FR-005**: System MUST allow tenants to upgrade to higher tiers with immediate prorated charge
- **FR-006**: System MUST allow tenants to downgrade with change effective at next billing cycle
- **FR-007**: System MUST provide self-service billing portal for payment method management
- **FR-008**: System MUST handle subscription cancellation with access until period end

**Feature Gating**:
- **FR-009**: System MUST define feature availability per tier in a centralized configuration
- **FR-010**: System MUST enforce feature access at the API endpoint level
- **FR-011**: System MUST display tier-appropriate UI elements (hide or show upgrade prompts)
- **FR-012**: System MUST provide clear upgrade prompts when users attempt to access gated features
- **FR-013**: System MUST support these feature flags: `ai_insights`, `client_portal`, `custom_triggers`, `api_access`, `knowledge_base`

**Client Limits**:
- **FR-014**: System MUST enforce client count limits per tier (Starter: 25, Professional: 100, Growth: 250, Enterprise: unlimited)
- **FR-015**: System MUST display current client usage vs. limit on dashboard
- **FR-016**: System MUST warn tenants when approaching limit (80% threshold)
- **FR-017**: System MUST block new client creation when limit is reached with upgrade prompt

**Billing Events**:
- **FR-018**: System MUST record all subscription lifecycle events (created, updated, cancelled)
- **FR-019**: System MUST record all payment events (succeeded, failed, refunded)
- **FR-020**: System MUST process Stripe webhooks for real-time event updates
- **FR-021**: System MUST handle webhook failures gracefully with retry logic

**Migration**:
- **FR-022**: System MUST migrate existing tenants to Professional tier with "grandfathered" status
- **FR-023**: System MUST preserve full feature access for grandfathered tenants
- **FR-024**: System MUST allow grandfathered tenants to optionally convert to paid subscription

### Key Entities

- **Subscription Tier**: Represents a pricing plan with name (starter/professional/growth/enterprise), monthly price, client limit, and included features
- **Tenant Subscription**: Links a tenant to their active subscription tier, Stripe customer ID, subscription status (active/past_due/cancelled/grandfathered), and current billing period
- **Feature Flag Config**: Defines which features are available at each tier level, used for gating decisions
- **Billing Event**: Records subscription and payment lifecycle events for audit and reporting
- **Client Usage**: Tracks current client count per tenant for limit enforcement

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Subscription changes affect tenant capabilities
- [x] **Data Access Events**: Billing information is sensitive financial data
- [x] **Data Modification Events**: Subscription tier changes affect access rights
- [ ] **Integration Events**: Stripe is external but payments are tracked separately
- [ ] **Compliance Events**: Not directly BAS-related but affects platform access

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| subscription.created | New subscription activated | tenant_id, tier, price, stripe_subscription_id | 7 years | None |
| subscription.upgraded | Tier increased | tenant_id, old_tier, new_tier, prorated_amount | 7 years | None |
| subscription.downgraded | Tier decreased | tenant_id, old_tier, new_tier, effective_date | 7 years | None |
| subscription.cancelled | Subscription ended | tenant_id, tier, reason, effective_date | 7 years | None |
| subscription.payment_failed | Payment declined | tenant_id, amount, failure_reason | 7 years | Card last 4 only |
| subscription.payment_succeeded | Payment processed | tenant_id, amount, invoice_id | 7 years | Card last 4 only |
| feature.access_denied | Gated feature blocked | tenant_id, feature_name, required_tier | 3 years | None |
| client_limit.warning | 80% limit reached | tenant_id, current_count, limit | 1 year | None |
| client_limit.blocked | Limit exceeded | tenant_id, current_count, limit | 3 years | None |

### Compliance Considerations

- **ATO Requirements**: Subscription billing is business expense - tenants may need invoices for tax deductions
- **Data Retention**: Billing records retained 7 years for financial compliance
- **Access Logging**: Only tenant owners and platform admins can view subscription details

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New tenants can complete subscription signup in under 3 minutes
- **SC-002**: 100% of subscription tier changes reflect immediately in feature access (within 5 seconds)
- **SC-003**: Upgrade prompts shown on all gated features result in 10%+ click-through rate
- **SC-004**: Payment success rate exceeds 95% for valid payment methods
- **SC-005**: Zero existing tenants lose access during migration to subscription system
- **SC-006**: Self-service billing portal usage reduces subscription support tickets by 80%
- **SC-007**: Client limit enforcement operates with zero false positives (blocking valid clients)
- **SC-008**: All billing events are captured and queryable within 1 minute of occurrence

## Assumptions

1. **Stripe Account**: A Stripe account is already configured for the platform
2. **Clerk Integration**: Existing Clerk authentication continues to identify tenant owners
3. **Single Currency**: All pricing is in AUD (Australian Dollars)
4. **Monthly Billing Only**: Annual billing is out of scope for initial release
5. **No Free Trial**: Trials are handled separately in Spec 021 (Onboarding Flow)
6. **Enterprise Custom**: Enterprise tier requires manual setup, not self-service
7. **Immediate Upgrades**: Upgrades take effect immediately with prorated charge
8. **Delayed Downgrades**: Downgrades take effect at next billing cycle to prevent abuse
