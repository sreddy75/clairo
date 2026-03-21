# Feature Specification: Admin Dashboard (Internal)

**Feature Branch**: `feature/022-admin-dashboard`
**Created**: 2026-01-01
**Status**: Draft
**Input**: User description: "Admin Dashboard (Internal) - Build an internal admin dashboard for Clairo operators to manage customers, monitor revenue, handle subscription management, and configure feature flags. The dashboard should provide visibility into all tenants (accounting practices), their subscription status, usage metrics, and revenue analytics (MRR, churn, expansion). It should allow manual tier changes, applying credits, and per-tenant feature flag overrides. This is an internal tool not exposed to customers."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - View All Customers (Priority: P1)

As a Clairo operator, I need to see all accounting practices (tenants) registered on the platform with their key metrics at a glance, so I can monitor the health of our customer base and identify practices that may need attention.

**Why this priority**: Core visibility into customers is the foundation of all admin operations. Without this, operators cannot perform any administrative tasks effectively.

**Independent Test**: Can be fully tested by loading the admin dashboard and verifying all registered tenants appear in a searchable, sortable list with their key metrics displayed.

**Acceptance Scenarios**:

1. **Given** I am an authenticated Clairo admin, **When** I access the admin dashboard, **Then** I see a paginated list of all tenants sorted by creation date (newest first)
2. **Given** I am viewing the tenant list, **When** I search by practice name or email, **Then** I see filtered results matching my search criteria
3. **Given** I am viewing the tenant list, **When** I filter by subscription tier or status, **Then** I see only tenants matching the selected filters
4. **Given** I am viewing a tenant in the list, **Then** I can see: practice name, owner email, subscription tier, subscription status, client count, last login date, and account age

---

### User Story 2 - Monitor Revenue Metrics (Priority: P1)

As a Clairo operator, I need to view key revenue metrics (MRR, churn, expansion) on a dashboard, so I can understand business health and identify revenue trends.

**Why this priority**: Revenue visibility is critical for business operations and strategic decision-making alongside customer visibility.

**Independent Test**: Can be fully tested by viewing the revenue dashboard section and verifying accurate calculations of MRR, churn, and expansion revenue.

**Acceptance Scenarios**:

1. **Given** I am on the admin dashboard, **When** I view the revenue section, **Then** I see current MRR (Monthly Recurring Revenue) calculated from active subscriptions
2. **Given** I am on the admin dashboard, **When** I view the revenue section, **Then** I see monthly churn rate (percentage of MRR lost from cancellations/downgrades)
3. **Given** I am on the admin dashboard, **When** I view the revenue section, **Then** I see expansion revenue (MRR gained from upgrades)
4. **Given** revenue metrics are displayed, **When** I select a date range, **Then** I see metrics recalculated for that period
5. **Given** I am viewing revenue metrics, **Then** I can see trend indicators (up/down arrows with percentage change vs previous period)

---

### User Story 3 - View Tenant Details (Priority: P2)

As a Clairo operator, I need to view detailed information about a specific tenant, so I can understand their usage patterns and make informed decisions about their account.

**Why this priority**: Detailed tenant view enables targeted support and informed decision-making, building on the list view.

**Independent Test**: Can be fully tested by clicking on a tenant from the list and verifying all detailed information displays correctly.

**Acceptance Scenarios**:

1. **Given** I am viewing the tenant list, **When** I click on a tenant, **Then** I see a detailed view with comprehensive account information
2. **Given** I am viewing tenant details, **Then** I see: subscription history, payment history, usage metrics (clients, syncs, AI queries), user accounts, and recent activity
3. **Given** I am viewing tenant details, **Then** I see feature flag status (which features are enabled/disabled for this tenant)
4. **Given** I am viewing tenant details, **Then** I see billing information including Stripe customer ID, subscription ID, and next billing date

---

### User Story 4 - Manage Subscriptions (Priority: P2)

As a Clairo operator, I need to manually change subscription tiers and apply credits to tenant accounts, so I can handle customer requests, promotions, and billing adjustments.

**Why this priority**: Direct subscription management enables customer support and sales operations without requiring Stripe dashboard access.

**Independent Test**: Can be fully tested by changing a tenant's tier and verifying the change propagates correctly to both the database and Stripe.

**Acceptance Scenarios**:

1. **Given** I am viewing a tenant's details, **When** I change their subscription tier, **Then** the change is recorded and takes effect immediately
2. **Given** I change a subscription tier, **When** I select a new tier, **Then** I must provide a reason for the change (audit trail)
3. **Given** I am viewing a tenant's details, **When** I apply a credit, **Then** I can specify the amount, reason, and whether it's a one-time or recurring credit
4. **Given** I apply a credit, **Then** the credit is reflected in the tenant's next invoice
5. **Given** I make any billing change, **Then** the change is logged with operator, timestamp, and reason

---

### User Story 5 - Configure Feature Flags (Priority: P3)

As a Clairo operator, I need to enable or disable specific features for individual tenants, so I can handle beta testing, special arrangements, or troubleshooting scenarios.

**Why this priority**: Feature flag overrides are less frequently needed but important for flexibility in handling edge cases.

**Independent Test**: Can be fully tested by toggling a feature flag for a tenant and verifying the feature behavior changes accordingly.

**Acceptance Scenarios**:

1. **Given** I am viewing a tenant's details, **When** I access feature flags, **Then** I see all available features with their current status (enabled/disabled/default)
2. **Given** I am viewing feature flags, **When** I override a flag, **Then** I can set it to enabled, disabled, or "use tier default"
3. **Given** I override a feature flag, **When** I save, **Then** I must provide a reason for the override
4. **Given** I override a feature flag, **Then** the override takes effect immediately without requiring tenant logout/login
5. **Given** a feature flag has been overridden, **Then** it is visually distinguished from tier-default flags

---

### User Story 6 - View Usage Analytics (Priority: P3)

As a Clairo operator, I need to see aggregate usage analytics across all tenants, so I can understand platform adoption and identify opportunities.

**Why this priority**: Aggregate analytics provide strategic insights but are less urgent than individual customer management.

**Independent Test**: Can be fully tested by viewing the analytics section and verifying aggregate metrics are correctly calculated.

**Acceptance Scenarios**:

1. **Given** I am on the admin dashboard, **When** I view usage analytics, **Then** I see aggregate metrics: total clients managed, total syncs performed, total AI queries
2. **Given** I am viewing usage analytics, **When** I select a tier filter, **Then** I see metrics broken down by subscription tier
3. **Given** I am viewing usage analytics, **When** I select a date range, **Then** I see usage trends over time
4. **Given** I am viewing usage analytics, **Then** I can identify top users (by clients, syncs, or AI usage)

---

### Edge Cases

- What happens when an operator tries to downgrade a tenant below their current client count?
  - System warns operator and requires confirmation, client data is preserved but new clients blocked
- What happens when Stripe is temporarily unavailable during a tier change?
  - System queues the change and retries, showing pending status to operator
- How does system handle operators attempting to modify their own tenant?
  - Self-modification is blocked with appropriate error message
- What happens when a tenant has a pending payment while tier is changed?
  - System warns operator about pending payment and requires explicit acknowledgment
- How are feature flag conflicts resolved (tier default vs override)?
  - Explicit overrides always take precedence over tier defaults

## Requirements *(mandatory)*

### Functional Requirements

**Authentication & Authorization**:
- **FR-001**: System MUST restrict admin dashboard access to users with "admin" or "super_admin" role
- **FR-002**: System MUST log all admin dashboard access attempts (successful and failed)
- **FR-003**: System MUST support role-based permissions (view-only vs full access)

**Tenant Management**:
- **FR-004**: System MUST display all registered tenants in a paginated, searchable list
- **FR-005**: System MUST allow filtering tenants by subscription tier, status, and date range
- **FR-006**: System MUST allow sorting tenants by name, created date, MRR, client count
- **FR-007**: System MUST display tenant details including: practice name, owner email, Stripe IDs, subscription info, usage metrics, and user accounts

**Revenue Analytics**:
- **FR-008**: System MUST calculate and display current MRR from active subscriptions
- **FR-009**: System MUST calculate monthly churn rate (lost MRR / starting MRR)
- **FR-010**: System MUST calculate expansion revenue (upgrades - downgrades)
- **FR-011**: System MUST show revenue trends with period-over-period comparison
- **FR-012**: System MUST allow date range selection for all revenue metrics

**Subscription Management**:
- **FR-013**: System MUST allow operators to change tenant subscription tier
- **FR-014**: System MUST sync tier changes with Stripe billing
- **FR-015**: System MUST allow operators to apply credits (one-time or recurring)
- **FR-016**: System MUST require reason/note for all billing changes
- **FR-017**: System MUST log all subscription changes with full audit trail

**Feature Flags**:
- **FR-018**: System MUST display all available feature flags per tenant
- **FR-019**: System MUST allow per-tenant feature flag overrides
- **FR-020**: System MUST distinguish between tier-default and overridden flags
- **FR-021**: System MUST require reason for feature flag overrides
- **FR-022**: System MUST apply flag changes immediately without requiring user action

**Usage Analytics**:
- **FR-023**: System MUST display aggregate platform usage metrics
- **FR-024**: System MUST allow filtering usage by tier and date range
- **FR-025**: System MUST identify top users by various metrics

### Key Entities

- **AdminUser**: An operator with admin privileges. Key attributes: user_id (links to existing User), role (admin/super_admin), permissions, created_at
- **BillingEvent**: Record of billing changes. Key attributes: tenant_id, event_type (tier_change, credit_applied, etc.), old_value, new_value, reason, operator_id, timestamp
- **FeatureFlagOverride**: Per-tenant feature override. Key attributes: tenant_id, feature_key, override_value (enabled/disabled/null for default), reason, operator_id, created_at
- **UsageSnapshot**: Periodic usage metrics. Key attributes: tenant_id, period (daily/monthly), client_count, sync_count, ai_query_count, snapshot_at

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Admin dashboard access requires authentication verification
- [x] **Data Access Events**: Viewing tenant details, billing info, and usage data must be logged
- [x] **Data Modification Events**: All tier changes, credits, and feature flag modifications
- [ ] **Integration Events**: N/A - This feature doesn't sync with external systems
- [ ] **Compliance Events**: N/A - This feature doesn't affect BAS lodgements

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| admin.dashboard.accessed | Admin loads dashboard | admin_id, IP, timestamp | 2 years | None |
| admin.tenant.viewed | Admin views tenant details | admin_id, tenant_id, timestamp | 2 years | None |
| admin.billing.tier_changed | Tier modification | admin_id, tenant_id, old_tier, new_tier, reason | 7 years | None |
| admin.billing.credit_applied | Credit applied | admin_id, tenant_id, amount, credit_type, reason | 7 years | None |
| admin.feature_flag.overridden | Flag override | admin_id, tenant_id, feature_key, old_value, new_value, reason | 2 years | None |
| admin.auth.failed | Failed admin access | user_id, IP, timestamp, failure_reason | 1 year | None |

### Compliance Considerations

- **ATO Requirements**: Not directly applicable - internal admin tool doesn't affect BAS/tax data
- **Data Retention**: Billing events retained for 7 years to match Stripe records; access logs for 2 years
- **Access Logging**: Audit logs viewable only by super_admin role

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Operators can locate any tenant and view their details within 30 seconds
- **SC-002**: Revenue metrics (MRR, churn, expansion) are calculated and displayed within 5 seconds of dashboard load
- **SC-003**: Tier changes propagate to Stripe within 10 seconds of operator action
- **SC-004**: 100% of admin actions are captured in audit logs
- **SC-005**: Operators can complete a tier change (including reason entry) in under 1 minute
- **SC-006**: Feature flag overrides take effect within 1 minute without requiring tenant action
- **SC-007**: Dashboard supports viewing 500+ tenants without performance degradation (page load under 3 seconds)

## Assumptions

1. Admin users are identified by a role in the existing User/PracticeUser model (no separate admin table needed)
2. Super_admin role has full access; admin role may have restricted access (view-only on certain operations)
3. The admin dashboard is a separate Next.js route protected by role-based middleware
4. Stripe integration already exists from Spec 019 - we extend it for manual tier changes
5. Feature flags configuration already exists from Spec 019 - we add override capability
6. Revenue metrics are calculated on-demand from Stripe data and cached for performance
7. The admin dashboard URL is not publicly linked and uses an obscure path (e.g., /internal/admin)
8. Rate limiting should be applied to prevent abuse of admin operations

## Scope Boundaries

### In Scope
- Tenant list view with search, filter, and sort
- Tenant detail view with comprehensive information
- Revenue dashboard (MRR, churn, expansion)
- Manual tier change capability
- Credit application
- Feature flag overrides per tenant
- Aggregate usage analytics
- Full audit logging

### Out of Scope
- Automated alerting (e.g., churn risk notifications) - future enhancement
- Bulk operations (e.g., change tier for multiple tenants at once)
- Direct Stripe dashboard integration (operators use our UI, not Stripe directly)
- Customer communication tools (emails, in-app messages)
- Financial forecasting or predictive analytics
- White-label admin features for enterprise customers
