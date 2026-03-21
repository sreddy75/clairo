# Feature Specification: Usage Tracking & Limits

**Feature Branch**: `feature/020-usage-tracking`
**Created**: 2025-12-31
**Status**: Draft
**Input**: User description: "Track and enforce usage limits per subscription tier. Implement real-time client count tracking, block new client creation when at tier limit, create usage dashboard showing clients/AI queries/documents processed, send overage alerts when approaching limits (80% threshold), and track usage analytics per tier for business insights. Builds on Spec 019's tier infrastructure."

---

## Overview

This feature builds on Spec 019's subscription tier infrastructure to add comprehensive usage tracking and limit enforcement. Accountants need visibility into their usage against tier limits, proactive alerts before hitting limits, and the platform needs analytics to understand usage patterns for business decisions.

**Key Value**: Prevent surprise lockouts by alerting users before they hit limits, provide transparency into usage, and enable data-driven tier recommendations.

---

## User Scenarios & Testing

### User Story 1 - View Usage Dashboard (Priority: P1)

As an accountant, I want to see my current usage against my tier limits so that I know how much capacity I have remaining and can plan accordingly.

**Why this priority**: This is the foundation - users need visibility before we can enforce limits or send alerts. Without a dashboard, users would have no idea why they're being blocked.

**Independent Test**: Can be fully tested by logging in and viewing the billing/usage page. Delivers immediate value by showing clients used vs limit.

**Acceptance Scenarios**:

1. **Given** I am logged in as an accountant with a Starter tier (25 client limit), **When** I navigate to the billing/usage page, **Then** I see a usage summary showing "Clients: 12 / 25" with a visual progress bar at 48%.

2. **Given** I am on the usage dashboard, **When** I view the usage breakdown, **Then** I see usage metrics for: clients connected, AI queries this month, and documents processed this month.

3. **Given** I have a Professional tier (100 client limit) with 95 clients, **When** I view the usage dashboard, **Then** I see a warning indicator showing I'm approaching my limit (95%).

4. **Given** I have an Enterprise tier (unlimited clients), **When** I view the usage dashboard, **Then** I see "Unlimited" instead of a numeric limit with no progress bar.

---

### User Story 2 - Client Limit Enforcement (Priority: P1)

As a platform operator, I want to block accountants from adding more clients than their tier allows so that tier limits are respected and users are prompted to upgrade.

**Why this priority**: Critical for monetization - without enforcement, tiers are meaningless. This is tied with US1 as core functionality.

**Independent Test**: Can be tested by attempting to add a client when at the limit. Delivers value by ensuring tier limits are enforced.

**Acceptance Scenarios**:

1. **Given** I am a Starter tier accountant with 25 clients (at limit), **When** I try to connect a new Xero contact as a client, **Then** I see an error message: "You've reached your 25 client limit. Upgrade to Professional for up to 100 clients."

2. **Given** I am at my client limit, **When** I try to add a client, **Then** the system shows an upgrade prompt with pricing for the next tier.

3. **Given** I am at my client limit, **When** I disconnect an existing client, **Then** I can immediately add a new client (freed up a slot).

4. **Given** I am a Professional tier with 50 clients (under 100 limit), **When** I try to add a new client, **Then** the operation succeeds and my client count updates to 51.

---

### User Story 3 - Approaching Limit Alerts (Priority: P2)

As an accountant, I want to receive alerts when I'm approaching my usage limits so that I can upgrade proactively and avoid disruption.

**Why this priority**: Improves user experience by preventing surprise blocks. Less critical than enforcement but important for retention.

**Independent Test**: Can be tested by having a tenant reach 80% of their limit and verifying an alert is sent.

**Acceptance Scenarios**:

1. **Given** I am a Starter tier accountant with 20 clients (80% of 25), **When** I add my 20th client, **Then** I receive an email notification: "You're at 80% of your client limit (20/25). Consider upgrading to avoid interruption."

2. **Given** I have already received an 80% alert, **When** I add more clients reaching 90% (23 clients), **Then** I receive another alert at 90% threshold.

3. **Given** I am at 75% of my limit, **When** I add a client, **Then** no alert is sent (below 80% threshold).

4. **Given** I already received an alert for 80%, **When** I check my dashboard, **Then** I see an in-app banner with the same warning and an upgrade button.

---

### User Story 4 - Usage Analytics for Admins (Priority: P3)

As a platform administrator, I want to see aggregate usage analytics across all tenants so that I can understand usage patterns and identify upsell opportunities.

**Why this priority**: Business intelligence - valuable but not user-facing. Can be built after core functionality.

**Independent Test**: Can be tested by accessing the admin dashboard and viewing aggregate statistics.

**Acceptance Scenarios**:

1. **Given** I am logged in as an admin, **When** I view the usage analytics page, **Then** I see aggregate stats: total clients across all tenants, average clients per tier, tenants at >80% limit.

2. **Given** I am on the analytics page, **When** I filter by tier, **Then** I see usage distribution for that specific tier.

3. **Given** there are tenants approaching limits, **When** I view the "upsell opportunities" section, **Then** I see a list of tenants at >80% of their limit with their current tier and email.

---

### User Story 5 - Usage History Tracking (Priority: P3)

As an accountant, I want to see my usage trends over time so that I can understand my growth and plan for future needs.

**Why this priority**: Nice-to-have for user insights. Not critical for MVP but adds value for planning.

**Independent Test**: Can be tested by viewing historical usage data on the dashboard.

**Acceptance Scenarios**:

1. **Given** I have been using the platform for 3 months, **When** I view usage history, **Then** I see a chart showing my client count over time (monthly data points).

2. **Given** I am viewing usage history, **When** I look at the trend, **Then** I can see if my usage is growing, stable, or declining.

---

### Edge Cases

- What happens when a tenant is downgraded and exceeds the new tier's limit?
  - Existing clients remain accessible (no data loss), but new clients cannot be added until under the limit.

- What happens when Xero sync adds contacts that would exceed the limit?
  - Sync should skip creating new clients beyond the limit and log a warning. Existing clients are updated normally.

- How are disconnected clients counted?
  - Disconnected clients (status = 'disconnected') do NOT count toward the limit. Only active connections count.

- What if a tenant has multiple Xero connections to the same business?
  - Each unique XeroConnection counts as one client regardless of contact duplication.

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST track real-time client count per tenant by counting active XeroConnections.

- **FR-002**: System MUST enforce client limits by blocking new client creation when at or above the tier limit.

- **FR-003**: System MUST display a usage dashboard showing: clients used/limit, AI queries this month, documents processed this month.

- **FR-004**: System MUST show a visual progress bar for usage metrics with color coding (green <60%, yellow 60-79%, orange 80-89%, red >=90%).

- **FR-005**: System MUST send email alerts when a tenant reaches 80% and 90% of their client limit.

- **FR-006**: System MUST display in-app banners when usage exceeds 80% threshold.

- **FR-007**: System MUST allow tenants at the limit to free up slots by disconnecting clients.

- **FR-008**: System MUST handle "unlimited" tiers (Enterprise) gracefully without progress bars or alerts.

- **FR-009**: System MUST track monthly usage metrics: AI queries (chat completions), documents processed (OCR/uploads).

- **FR-010**: System MUST persist usage snapshots for historical trend analysis.

- **FR-011**: System MUST provide admin view of aggregate usage across all tenants.

- **FR-012**: System MUST identify "upsell opportunities" (tenants at >80% of limit) for admin review.

### Key Entities

- **UsageSnapshot**: Point-in-time record of a tenant's usage (client_count, ai_queries_count, documents_count, captured_at).

- **UsageAlert**: Record of alerts sent to tenants (tenant_id, alert_type, threshold_percentage, sent_at).

- **TenantUsageMetrics**: Aggregated current usage for a tenant (updated on each relevant action).

---

## Auditing & Compliance Checklist

### Audit Events Required

- [ ] **Authentication Events**: No - this feature does not change authentication.
- [x] **Data Access Events**: Yes - viewing usage data should be logged for admin transparency.
- [x] **Data Modification Events**: Yes - alert sending and usage snapshot creation should be logged.
- [ ] **Integration Events**: No - no external system integration.
- [ ] **Compliance Events**: No - not directly related to BAS lodgement.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| usage.dashboard.viewed | User views usage dashboard | tenant_id, user_id, timestamp | 1 year | None |
| usage.limit.reached | Tenant hits client limit | tenant_id, current_count, limit, tier | 5 years | None |
| usage.alert.sent | Threshold alert email sent | tenant_id, alert_type, threshold, recipient_email | 5 years | Email (no masking needed) |
| usage.snapshot.created | Monthly usage snapshot saved | tenant_id, metrics snapshot | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: None specific - usage tracking is operational, not compliance-related.
- **Data Retention**: Usage snapshots retained for 7 years to match ATO record-keeping requirements.
- **Access Logging**: Admins accessing usage analytics should be logged for internal audit purposes.

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can view their current usage within 2 seconds of navigating to the billing page.

- **SC-002**: 100% of client creation attempts at the limit are blocked with an appropriate error message.

- **SC-003**: 95% of tenants approaching their limit (80%+) receive an email alert within 5 minutes.

- **SC-004**: Usage dashboard accurately reflects client count within 1 minute of changes.

- **SC-005**: 90% of users at >80% limit click through to view upgrade options (measured via analytics).

- **SC-006**: Zero data loss - existing clients remain accessible even when a tenant exceeds their limit due to downgrade.

- **SC-007**: Admin dashboard loads aggregate usage for all tenants within 3 seconds.

---

## Assumptions

1. **Client count source**: Client count is derived from `xero_connections` table where `status != 'disconnected'`. This is already implemented in Spec 019.

2. **AI query tracking**: AI queries are counted per chat completion request. This requires adding a counter to the existing chat endpoint.

3. **Document tracking**: Document count tracks uploads/OCR processing events. This may require adding hooks to existing document processing.

4. **Alert frequency**: Alerts are sent once per threshold (80%, 90%) per billing period. Resetting monthly prevents alert fatigue.

5. **Historical data**: Usage snapshots are taken daily and aggregated to monthly for history view.

6. **Email infrastructure**: Email sending infrastructure already exists from Spec 019 (Stripe notifications) and can be reused.

---

## Dependencies

- **Spec 019**: Subscription & Feature Gating - provides tier infrastructure, client limits, and billing module.
- **Existing XeroConnection model**: Used to count active clients per tenant.
- **Email notification system**: For sending threshold alerts.

---

## Out of Scope

- Overage billing (charging for clients above the limit) - future consideration.
- Real-time usage alerts via push notifications - email only for now.
- Per-feature usage limits (e.g., AI query limits) - only client limits enforced in this spec.
- Usage-based pricing adjustments - tiers have fixed limits.
