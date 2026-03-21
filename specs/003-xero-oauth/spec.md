# Feature Specification: Xero OAuth & Connection Management

**Feature Branch**: `feature/003-xero-oauth`
**Created**: 2025-12-28
**Status**: Draft
**Input**: ROADMAP.md - Phase 1 (M1: Single Client View)

---

## Overview

Enable Clairo users to connect their Xero organizations to the platform using OAuth 2.0, establishing the foundation for financial data synchronization. This is the first step in the Data Pillar - without Xero connection, no client financial data can flow into the system.

---

## User Scenarios & Testing

### User Story 1 - Connect Xero Organization (Priority: P1)

As an accountant, I want to connect my Xero account to Clairo so that I can access my clients' financial data for BAS preparation.

**Why this priority**: This is the foundational capability - without Xero connection, the entire Data Pillar cannot function. Every subsequent feature (data sync, BAS preparation) depends on this.

**Independent Test**: User can click "Connect Xero", complete OAuth flow, and see their connected Xero organization listed in Clairo. Can be fully tested end-to-end with a Xero demo account.

**Acceptance Scenarios**:

1. **Given** I am logged in to Clairo, **When** I click "Connect Xero" on the settings page, **Then** I am redirected to Xero's authorization page with the correct scopes requested.

2. **Given** I am on Xero's authorization page, **When** I approve the connection for one of my organizations, **Then** I am redirected back to Clairo and the organization appears in my connected accounts.

3. **Given** I have multiple Xero organizations, **When** I complete the OAuth flow, **Then** I can select which organization(s) to connect to Clairo.

4. **Given** I am redirected back from Xero, **When** the authorization code is exchanged for tokens, **Then** the access token and refresh token are securely stored and associated with my tenant.

---

### User Story 2 - View and Manage Connections (Priority: P1)

As an accountant, I want to view my connected Xero organizations and manage them so that I can see connection status and remove connections when needed.

**Why this priority**: Users must be able to see what's connected and manage connections. Essential for trust and control over their data.

**Independent Test**: User can view list of connected Xero organizations with status indicators, and can disconnect an organization.

**Acceptance Scenarios**:

1. **Given** I have connected Xero organizations, **When** I navigate to Settings > Integrations, **Then** I see a list of all connected organizations with their names and connection status.

2. **Given** I have a connected organization, **When** I click "Disconnect", **Then** the connection is removed, tokens are deleted, and the organization no longer appears in my list.

3. **Given** I have a connected organization, **When** the connection has an issue (expired tokens that can't refresh), **Then** I see a warning indicator and a prompt to reconnect.

4. **Given** I have no connected organizations, **When** I view the integrations page, **Then** I see a clear call-to-action to connect Xero with explanation of benefits.

---

### User Story 3 - Automatic Token Refresh (Priority: P1)

As a system, I need to automatically refresh Xero access tokens so that users don't have to manually reconnect and data sync continues uninterrupted.

**Why this priority**: Access tokens expire every 30 minutes. Without automatic refresh, the system would be unusable. This is infrastructure-critical.

**Independent Test**: System automatically refreshes tokens before expiry without user intervention; background sync continues working.

**Acceptance Scenarios**:

1. **Given** an access token is about to expire (within 5 minutes), **When** an API call is needed, **Then** the system automatically refreshes the token before making the call.

2. **Given** a refresh token is used, **When** new tokens are received, **Then** the new refresh token replaces the old one (rotating tokens) and both tokens are securely stored.

3. **Given** a refresh attempt fails due to network error, **When** retrying within 30 minutes, **Then** the system can retry with the same refresh token.

4. **Given** a refresh token has expired (60 days unused or 30 days since last use), **When** a refresh is attempted, **Then** the system marks the connection as requiring re-authorization and notifies the user.

---

### User Story 4 - Multi-Tenant Connection Isolation (Priority: P2)

As a practice with multiple users, I want Xero connections to be tenant-scoped so that each practice's connections are isolated and secure.

**Why this priority**: Security requirement - connections must be tenant-isolated to prevent cross-tenant data access. Important but leverages existing RLS infrastructure.

**Independent Test**: Two different tenants can each have Xero connections; neither can see or access the other's connections.

**Acceptance Scenarios**:

1. **Given** Tenant A has connected Organization X, **When** User from Tenant B accesses integrations, **Then** they cannot see Organization X.

2. **Given** multiple users in the same tenant, **When** any user views integrations, **Then** they see all connections for their tenant (based on role permissions).

3. **Given** a tenant connection exists, **When** queried via the API, **Then** RLS ensures only the owning tenant can access the connection details.

---

### User Story 5 - Rate Limit Handling (Priority: P2)

As a system, I need to handle Xero API rate limits gracefully so that the integration remains stable under load.

**Why this priority**: Xero has strict rate limits (60/min, 5000/day per tenant). Without proper handling, the system would fail unpredictably.

**Independent Test**: System respects rate limits, queues requests when approaching limits, and implements exponential backoff on 429 responses.

**Acceptance Scenarios**:

1. **Given** an API response includes rate limit headers, **When** X-MinLimit-Remaining approaches zero, **Then** the system pauses requests for that tenant until the limit resets.

2. **Given** a 429 (Too Many Requests) response is received, **When** the Retry-After header indicates 30 seconds, **Then** the system waits at least 30 seconds before retrying.

3. **Given** multiple requests are queued, **When** processing the queue, **Then** the system uses exponential backoff to avoid persistent throttling.

4. **Given** rate limit state, **When** checked programmatically, **Then** remaining calls are available for scheduling decisions.

---

### User Story 6 - Connection Security and Audit (Priority: P2)

As a regulated accounting practice, I need all Xero connection activities to be audited so that I can demonstrate compliance and track access.

**Why this priority**: ATO compliance requires audit trails. All connection/disconnection events and token operations must be logged.

**Independent Test**: Connection events appear in audit log with actor, timestamp, and action details.

**Acceptance Scenarios**:

1. **Given** a user connects a Xero organization, **When** the connection completes, **Then** an audit event `integration.xero.connected` is logged with organization ID and user.

2. **Given** a user disconnects a Xero organization, **When** the disconnection completes, **Then** an audit event `integration.xero.disconnected` is logged.

3. **Given** an automatic token refresh occurs, **When** the refresh completes or fails, **Then** an audit event is logged (success or failure reason).

4. **Given** a connection requires re-authorization, **When** the system detects this, **Then** an audit event `integration.xero.authorization_required` is logged.

---

### Edge Cases

- What happens when user cancels on Xero authorization page? (Graceful redirect back with error message)
- What happens when OAuth state parameter doesn't match? (Reject callback, log security event)
- What happens when Xero organization is disconnected from Xero side? (Detect on next API call, mark as requiring re-auth)
- What happens during concurrent token refresh attempts? (Locking mechanism to prevent race conditions)
- What happens if user connects same Xero org to multiple Clairo tenants? (Allowed - each tenant has its own connection)

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST implement OAuth 2.0 Authorization Code flow with PKCE for Xero authentication
- **FR-002**: System MUST request the following Xero scopes: `offline_access`, `openid`, `profile`, `email`, `accounting.settings`, `accounting.transactions`, `accounting.contacts`, `accounting.reports.read`
- **FR-003**: System MUST securely store access tokens and refresh tokens encrypted at rest
- **FR-004**: System MUST automatically refresh access tokens before they expire (30-minute lifetime)
- **FR-005**: System MUST handle Xero's rotating refresh tokens (each refresh token is single-use)
- **FR-006**: System MUST support connecting multiple Xero organizations per tenant
- **FR-007**: System MUST enforce tenant isolation on all Xero connections using RLS
- **FR-008**: System MUST handle rate limits: 60 calls/minute per tenant, 5000 calls/day per tenant
- **FR-009**: System MUST track rate limit remaining via response headers (X-DayLimit-Remaining, X-MinLimit-Remaining)
- **FR-010**: System MUST implement exponential backoff on 429 responses with Retry-After header
- **FR-011**: System MUST provide UI for connecting, viewing, and disconnecting Xero organizations
- **FR-012**: System MUST display connection status (active, needs re-auth, error) for each organization
- **FR-013**: System MUST log all connection lifecycle events to audit log
- **FR-014**: System MUST validate OAuth state parameter to prevent CSRF attacks
- **FR-015**: System MUST handle the case where Xero organization access is revoked externally

### Non-Functional Requirements

- **NFR-001**: Token refresh MUST complete in under 2 seconds
- **NFR-002**: Connection list page MUST load in under 500ms
- **NFR-003**: OAuth callback MUST be processed within 5 seconds
- **NFR-004**: Encrypted token storage MUST use AES-256 or equivalent
- **NFR-005**: Rate limit state MUST be persisted (survive server restarts)

### Key Entities

- **XeroConnection**: Represents a link between a Clairo tenant and a Xero organization
  - tenant_id (FK), xero_tenant_id (Xero's org ID), organization_name, connection_status
  - access_token (encrypted), refresh_token (encrypted), token_expires_at
  - rate_limit_remaining_daily, rate_limit_remaining_minute, rate_limit_reset_at
  - connected_at, connected_by, last_used_at

- **XeroConnectionEvent**: Audit trail for connection lifecycle
  - connection_id (FK), event_type, event_data, created_at

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Authentication Events**: OAuth flow completion, token refresh
- [ ] **Data Access Events**: Not applicable for this spec (data sync is Spec 004)
- [x] **Data Modification Events**: Connection created, updated, deleted
- [x] **Integration Events**: Xero API calls, rate limit events, errors
- [ ] **Compliance Events**: Not applicable for this spec

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `integration.xero.connected` | OAuth flow complete | org_id, org_name, scopes, user_id | 7 years | None |
| `integration.xero.disconnected` | User disconnects | org_id, org_name, user_id, reason | 7 years | None |
| `integration.xero.token_refreshed` | Auto token refresh | org_id, success/failure | 5 years | None |
| `integration.xero.authorization_required` | Refresh fails | org_id, failure_reason | 5 years | None |
| `integration.xero.rate_limited` | 429 received | org_id, endpoint, retry_after | 5 years | None |
| `integration.xero.oauth_state_mismatch` | CSRF attempt | request_ip, expected_state_hash | 7 years | IP masked to /24 |

### Compliance Considerations

- **ATO Requirements**: Connection history must be retained for audit trail of data source
- **Data Retention**: Token metadata retained 7 years, actual tokens deleted on disconnect
- **Access Logging**: Admin users can view audit logs for their tenant's connections

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: Users can complete Xero OAuth connection in under 60 seconds (excluding time on Xero's site)
- **SC-002**: Token refresh success rate > 99.9% when refresh token is valid
- **SC-003**: Zero cross-tenant data leakage in security testing
- **SC-004**: 100% of connection lifecycle events captured in audit log
- **SC-005**: System handles rate limits gracefully with zero unhandled 429 errors in production

---

## API Endpoints Design

### Backend Endpoints

| Method | Path | Description | Auth |
|--------|------|-------------|------|
| GET | `/api/v1/integrations/xero/auth-url` | Generate OAuth authorization URL with PKCE | JWT |
| GET | `/api/v1/integrations/xero/callback` | Handle OAuth callback, exchange code for tokens | None (state validation) |
| GET | `/api/v1/integrations/xero/connections` | List connected Xero organizations | JWT |
| GET | `/api/v1/integrations/xero/connections/{id}` | Get connection details | JWT |
| DELETE | `/api/v1/integrations/xero/connections/{id}` | Disconnect Xero organization | JWT (Admin) |
| POST | `/api/v1/integrations/xero/connections/{id}/refresh` | Manually trigger token refresh | JWT (Admin) |

### Frontend Routes

| Path | Description |
|------|-------------|
| `/settings/integrations` | List all integrations (Xero, future MYOB) |
| `/settings/integrations/xero` | Xero-specific connection management |
| `/settings/integrations/xero/callback` | OAuth callback landing page |

---

## Technical Considerations

### Xero OAuth 2.0 Specifics

- **Authorization URL**: `https://login.xero.com/identity/connect/authorize`
- **Token URL**: `https://identity.xero.com/connect/token`
- **Tenants URL**: `https://api.xero.com/connections` (list connected organizations)
- **Token Lifetime**: Access tokens expire after 30 minutes
- **Refresh Token**: Valid for 60 days, single-use (rotating), expires after 30 days of inactivity

### PKCE Flow

1. Generate code_verifier (random 43-128 character string)
2. Generate code_challenge = BASE64URL(SHA256(code_verifier))
3. Include code_challenge in authorization request
4. Include code_verifier in token exchange request

### Rate Limit Headers

```
X-DayLimit-Remaining: 4995
X-MinLimit-Remaining: 58
X-AppMinLimit-Remaining: 9995
Retry-After: 30
```

---

## Dependencies

- **Spec 002 (Complete)**: Auth & Multi-tenancy - provides tenant context, RLS, audit infrastructure
- **Blocked by this spec**: Spec 004 (Xero Data Sync), Spec 005 (Single Client View)

---

## References

- [Xero OAuth 2.0 Overview](https://developer.xero.com/documentation/guides/oauth2/overview/)
- [Xero PKCE Flow](https://developer.xero.com/documentation/guides/oauth2/pkce-flow)
- [Xero OAuth Scopes](https://developer.xero.com/documentation/guides/oauth2/scopes/)
- [Xero Rate Limits](https://developer.xero.com/documentation/guides/oauth2/limits/)
