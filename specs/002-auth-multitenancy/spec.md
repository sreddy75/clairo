# Feature Specification: Auth & Multi-tenancy

**Feature Branch**: `feature/002-auth`
**Created**: 2025-12-28
**Status**: Draft
**Spec ID**: 002
**Phase**: Phase 0 (M0: Foundation)
**Release**: R1 (Layer 1 - Core BAS)

---

## Introduction

This specification defines the authentication and multi-tenancy foundation for Clairo. As a platform serving multiple accounting practices (tenants), each with their own clients and data, robust authentication and complete tenant isolation are critical security requirements.

The system supports two distinct user types:
1. **Accountants** - Full platform access authenticated via Clerk
2. **Business Owners** - Portal-only access via magic link (Layer 2, future spec)

This spec focuses on accountant authentication and the multi-tenant infrastructure that will support both user types. Row-Level Security (RLS) at the PostgreSQL level ensures that tenant data can never cross boundaries, even in the case of application-level bugs.

**Key Outcomes:**
- Secure JWT-based authentication with Clerk integration
- Complete tenant isolation via PostgreSQL RLS
- Role-based access control (Admin, Accountant, Staff)
- Audit trail for all authentication and authorization events

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Accountant Registration and First Login (Priority: P1)

A new accountant signs up for Clairo to manage their accounting practice. They complete registration through Clerk, which creates their user account and provisions a new tenant (accounting practice). Upon first login, they see an empty dashboard ready for client setup.

**Why this priority**: Without working registration and login, no other functionality is accessible. This is the gateway to the entire platform.

**Independent Test**: Can be fully tested by completing the registration flow and verifying the user can access their empty dashboard. Delivers value as the first step for any new user.

**Acceptance Scenarios**:

1. **Given** a new user on the registration page, **When** they complete Clerk registration with valid email and password, **Then** the system creates a new user record, provisions a new tenant, assigns the user as Admin, and redirects to the dashboard.

2. **Given** a user with an existing Clerk account, **When** they attempt to register again with the same email, **Then** Clerk prevents duplicate registration and displays an appropriate error.

3. **Given** a newly registered user, **When** they log in for the first time, **Then** the system creates a valid JWT session with tenant_id embedded in the token claims.

4. **Given** a user on the login page, **When** they enter invalid credentials, **Then** Clerk displays an error message and the login attempt is logged in the audit trail.

5. **Given** a logged-in user, **When** they access any API endpoint, **Then** the request includes a valid JWT and the backend validates the token signature and expiration.

---

### User Story 2 - Tenant Data Isolation (Priority: P1)

An accountant from Practice A logs in and views their clients. They should only see clients belonging to their practice, never clients from Practice B. Even if a bug exists in the application code, the database-level RLS policies prevent cross-tenant data access.

**Why this priority**: Multi-tenancy is a foundational security requirement. Without complete isolation, the platform cannot be trusted with sensitive financial data.

**Independent Test**: Can be tested by creating two tenants with data, logging in as each, and verifying data isolation at both API and database levels.

**Acceptance Scenarios**:

1. **Given** two tenants (Practice A and Practice B) each with clients, **When** a user from Practice A queries the clients API, **Then** they receive only Practice A clients with zero Practice B data visible.

2. **Given** a valid JWT for Tenant A, **When** a malformed API request attempts to specify a different tenant_id in the request body, **Then** the system ignores the request body tenant_id and uses the JWT-embedded tenant_id.

3. **Given** PostgreSQL RLS is enabled on the clients table, **When** a database query is executed without setting the tenant context, **Then** the query returns zero rows regardless of data in the table.

4. **Given** a user authenticated as Tenant A, **When** they attempt to access a specific resource URL belonging to Tenant B (e.g., `/api/v1/clients/{tenant_b_client_id}`), **Then** the system returns 404 Not Found (not 403) to prevent tenant enumeration.

5. **Given** a database administrator with direct DB access, **When** they query tenant-scoped tables, **Then** RLS policies require explicit tenant context or superuser override.

---

### User Story 3 - Role-Based Access Control within a Tenant (Priority: P2)

A practice administrator invites team members with different roles. Admins can manage users and billing, Accountants can manage clients and BAS, and Staff have read-only access for support tasks.

**Why this priority**: Role differentiation is essential for multi-user practices but not required for single-user MVP. After authentication and tenant isolation work, RBAC enables team collaboration.

**Independent Test**: Can be tested by creating users with different roles and verifying access control at each permission level.

**Acceptance Scenarios**:

1. **Given** an Admin user, **When** they access user management endpoints, **Then** they can invite, modify roles, and deactivate users within their tenant.

2. **Given** an Accountant user, **When** they attempt to access user management endpoints, **Then** they receive 403 Forbidden and an audit event is logged.

3. **Given** a Staff user, **When** they access client data endpoints, **Then** they can read client information but cannot create, update, or delete clients.

4. **Given** any role, **When** they attempt an action beyond their permission level, **Then** the denied action is logged in the audit trail with role and attempted action.

5. **Given** an Admin user, **When** they change another user's role, **Then** the change takes effect immediately and is logged with before/after values.

---

### User Story 4 - JWT Token Management (Priority: P2)

Clerk issues access tokens for the frontend. The backend validates these tokens, extracts user and tenant context, and sets up the request context for RLS and auditing.

**Why this priority**: Token management is the bridge between Clerk authentication and backend authorization. Required for any authenticated API call.

**Independent Test**: Can be tested by validating token handling for various scenarios (valid, expired, tampered, missing).

**Acceptance Scenarios**:

1. **Given** a valid Clerk JWT, **When** the backend receives an API request, **Then** it validates the signature using Clerk's public JWKS endpoint and extracts claims.

2. **Given** an expired JWT, **When** the backend receives an API request, **Then** it returns 401 Unauthorized with an error indicating token expiration.

3. **Given** a JWT with an invalid signature, **When** the backend receives an API request, **Then** it returns 401 Unauthorized and logs a security event.

4. **Given** a valid JWT, **When** claims are extracted, **Then** the middleware sets tenant_id and user_id in the request context for downstream use.

5. **Given** a request without an Authorization header, **When** accessing a protected endpoint, **Then** the system returns 401 Unauthorized.

6. **Given** the Clerk JWKS endpoint is temporarily unavailable, **When** validating a token, **Then** the system uses cached JWKS keys with a fallback retry mechanism.

---

### User Story 5 - Tenant Middleware and Context Propagation (Priority: P2)

Every authenticated request passes through tenant middleware that establishes the security context for the entire request lifecycle. This context is available to all services, repositories, and audit logging.

**Why this priority**: Middleware is the enforcement point for tenant isolation. Without it, every service would need to implement isolation logic independently.

**Independent Test**: Can be tested by tracing request context through the middleware chain and verifying it's available in services and repositories.

**Acceptance Scenarios**:

1. **Given** a valid authenticated request, **When** it passes through tenant middleware, **Then** the PostgreSQL session variable `app.current_tenant_id` is set for RLS enforcement.

2. **Given** the request context is established, **When** any service retrieves the current tenant, **Then** it receives the same tenant_id extracted from the JWT.

3. **Given** a request in progress, **When** an audit event is logged, **Then** the event automatically includes tenant_id, user_id, and request_id from the context.

4. **Given** multiple concurrent requests from different tenants, **When** processed in parallel, **Then** each request maintains isolated context without cross-contamination.

5. **Given** a request that throws an exception, **When** the middleware handles cleanup, **Then** it properly clears the tenant context to prevent leakage.

---

### User Story 6 - User Invitation and Onboarding (Priority: P3)

An Admin invites a new team member by email. The invitee receives an email with a link to complete registration via Clerk. Upon completion, they are automatically associated with the inviting tenant with the specified role.

**Why this priority**: Team growth is important but not critical for single-user pilot. This enables scaling within a practice.

**Independent Test**: Can be tested end-to-end by sending an invitation and completing the onboarding flow.

**Acceptance Scenarios**:

1. **Given** an Admin user, **When** they create an invitation for "new@example.com" with role "Accountant", **Then** the system creates a pending invitation record and triggers an invitation email.

2. **Given** a pending invitation, **When** the invitee clicks the email link and completes Clerk registration, **Then** they are automatically linked to the tenant with the specified role.

3. **Given** a pending invitation, **When** it is not accepted within 7 days, **Then** the invitation expires and cannot be used.

4. **Given** an expired or revoked invitation link, **When** accessed, **Then** the user sees a clear message that the invitation is no longer valid.

5. **Given** an invitation for an email that already exists in the system, **When** created, **Then** the system returns an error indicating the user already has an account.

---

### User Story 7 - Session Management and Logout (Priority: P3)

Users can view their active sessions, logout from the current device, or logout from all devices for security purposes. All session events are audited.

**Why this priority**: Important for security hygiene but not critical for MVP functionality.

**Independent Test**: Can be tested by logging in from multiple devices and verifying session controls work correctly.

**Acceptance Scenarios**:

1. **Given** a logged-in user, **When** they click logout, **Then** Clerk revokes the current session and the user is redirected to the login page.

2. **Given** a user with multiple active sessions, **When** they view active sessions, **Then** they see a list with device info, IP address (masked), and last activity time.

3. **Given** a user with multiple active sessions, **When** they click "logout all devices", **Then** all sessions are revoked and a security audit event is logged.

4. **Given** a revoked session token, **When** used for an API request, **Then** the backend returns 401 Unauthorized.

5. **Given** any logout event, **When** it occurs, **Then** an audit event is logged with session details for compliance.

---

### User Story 8 - MFA Enforcement (Priority: P3)

Practice administrators can require MFA for all users in their tenant. Individual users can enable MFA even if not required. MFA status and changes are audited.

**Why this priority**: Enhanced security for practices handling sensitive financial data. Not required for initial pilot but important for enterprise practices.

**Independent Test**: Can be tested by enabling MFA requirement and verifying enforcement during login.

**Acceptance Scenarios**:

1. **Given** a tenant with MFA required, **When** a user without MFA attempts to access the platform, **Then** they are redirected to MFA setup before proceeding.

2. **Given** a user setting up MFA, **When** they complete authenticator app setup via Clerk, **Then** subsequent logins require the second factor.

3. **Given** a user with MFA enabled, **When** they enter an incorrect MFA code 5 times, **Then** their account is temporarily locked and an alert is triggered.

4. **Given** MFA status change, **When** enabled or disabled, **Then** an audit event is logged with the change details.

5. **Given** an Admin, **When** they toggle the tenant MFA requirement, **Then** the setting change is logged and all users without MFA are prompted on next login.

---

### Edge Cases

- What happens when a user's tenant is suspended? They should receive a clear error and be unable to access any resources.
- How does the system handle JWT clock skew? Allow a configurable tolerance (default 60 seconds) for token expiration validation.
- What happens if a user is deactivated mid-session? Active sessions should be revoked immediately.
- How does the system handle database connection failures? Fail closed - deny access if tenant context cannot be established.
- What happens during Clerk outages? Graceful degradation with cached JWKS; new logins may be unavailable but existing sessions continue.

---

## Requirements *(mandatory)*

### Functional Requirements

**Authentication:**
- **FR-001**: System MUST authenticate accountants via Clerk using OAuth 2.0 / OIDC protocols
- **FR-002**: System MUST validate JWT tokens using Clerk's public JWKS endpoint
- **FR-003**: System MUST cache JWKS keys with a configurable TTL (default: 1 hour) and refresh mechanism
- **FR-004**: System MUST reject expired, malformed, or invalid signature tokens with 401 response
- **FR-005**: System MUST extract user_id, tenant_id, email, and roles from validated JWT claims

**Multi-tenancy:**
- **FR-006**: System MUST store tenant_id on all tenant-scoped database tables
- **FR-007**: System MUST implement PostgreSQL Row-Level Security (RLS) on all tenant-scoped tables
- **FR-008**: System MUST set PostgreSQL session variable `app.current_tenant_id` for each authenticated request
- **FR-009**: System MUST prevent cross-tenant data access at the database level regardless of application logic
- **FR-010**: System MUST return 404 (not 403) when accessing resources from other tenants to prevent enumeration

**Role-Based Access Control:**
- **FR-011**: System MUST support three roles: Admin, Accountant, Staff
- **FR-012**: System MUST enforce role-based permissions using FastAPI dependency injection
- **FR-013**: Admin role MUST have full access including user management and tenant settings
- **FR-014**: Accountant role MUST have full access to client and BAS operations but not user management
- **FR-015**: Staff role MUST have read-only access to client data
- **FR-016**: System MUST log all permission denied events with role and attempted action

**Session Management:**
- **FR-017**: System MUST support logout from current session via Clerk
- **FR-018**: System MUST support logout from all sessions
- **FR-019**: System MUST immediately revoke access for deactivated users

**User Management:**
- **FR-020**: Admin users MUST be able to invite new users via email with a specified role
- **FR-021**: Invitations MUST expire after a configurable period (default: 7 days)
- **FR-022**: System MUST prevent duplicate invitations to the same email
- **FR-023**: System MUST support role changes by Admin users

**MFA:**
- **FR-024**: System MUST support tenant-level MFA requirement configuration
- **FR-025**: System MUST support individual user MFA setup via Clerk
- **FR-026**: System MUST enforce MFA requirement before granting access to protected resources

### Non-Functional Requirements

- **NFR-001**: JWT validation MUST complete within 50ms (P95) excluding network latency to JWKS
- **NFR-002**: JWKS key rotation MUST be handled transparently without service interruption
- **NFR-003**: Tenant context middleware MUST add less than 5ms overhead per request
- **NFR-004**: RLS policies MUST not degrade query performance by more than 10% compared to non-RLS queries
- **NFR-005**: System MUST handle 1000 concurrent authenticated users per tenant without degradation
- **NFR-006**: Failed login attempts MUST be rate-limited (max 5 per minute per email)

### Key Entities

> **Design Pattern**: Shared Identity + Separate Profiles
> This pattern supports multiple user types (Practice Users now, Business Owners in Layer 2) with a single identity table and type-specific profile tables.

- **Tenant**: An accounting practice organization. Has id, name, slug, settings (JSONB including MFA requirement), subscription_status, is_active, created_at, updated_at. All tenant-scoped data references this entity.

- **User** (Base Identity): Core identity for ALL user types. Has id, email (unique), user_type (enum: PRACTICE_USER, BUSINESS_OWNER), is_active, created_at, updated_at. This is the single source of truth for "who can authenticate".

- **PracticeUser** (Profile for Accountants): Practice staff profile, 1:1 with User where user_type=PRACTICE_USER. Has id, user_id (FK unique), tenant_id (FK), clerk_id (unique), role (enum: Admin, Accountant, Staff), mfa_enabled, last_login_at, created_at, updated_at.

- **ClientUser** (Profile for Business Owners - Layer 2): Business owner profile, 1:1 with User where user_type=BUSINESS_OWNER. Has id, user_id (FK unique), client_id (FK to clients table), magic_link_token, magic_link_expires_at, last_login_at. *Implementation deferred to Spec 012.*

- **Invitation**: A pending user invitation. Has id, tenant_id (FK), email, role, invited_by (FK to PracticeUser), token (unique), expires_at, accepted_at, created_at.

- **Session**: Tracked for audit purposes (managed by Clerk for practice users, by Clairo for client users). Audit logs reference session_id for correlation.

---

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Does this feature involve user authentication or authorization changes?
  - Login success/failure, logout, MFA events, password changes (via Clerk webhooks)
- [x] **Data Access Events**: Does this feature read sensitive data (TFN, bank details, BAS figures)?
  - No direct sensitive data access in auth module, but establishes audit context
- [x] **Data Modification Events**: Does this feature create, update, or delete business-critical data?
  - User creation, role changes, tenant settings changes
- [ ] **Integration Events**: Does this feature sync with external systems (Xero, MYOB, ATO)?
  - Not applicable to auth module
- [ ] **Compliance Events**: Does this feature affect BAS lodgements or compliance status?
  - Not directly, but auth is prerequisite for all compliance actions

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `auth.login.success` | Successful authentication | user_id, tenant_id, IP, user_agent, session_id | 7 years | IP masked to /24 |
| `auth.login.failure` | Failed authentication | email (masked), IP, failure_reason | 7 years | Email shows first 3 chars |
| `auth.logout` | User logout | user_id, tenant_id, session_id, logout_type (single/all) | 7 years | None |
| `auth.mfa.enabled` | MFA setup completed | user_id, tenant_id, mfa_method | 7 years | None |
| `auth.mfa.disabled` | MFA removed | user_id, tenant_id, disabled_by | 7 years | None |
| `auth.mfa.failed` | MFA verification failed | user_id, attempt_count, IP | 7 years | None |
| `auth.password.changed` | Password change (via Clerk webhook) | user_id, tenant_id | 7 years | Never log password |
| `auth.token.invalid` | Invalid token rejected | IP, token_error_type, partial_claims | 7 years | Token not logged |
| `user.created` | New user registration/invitation accepted | user_id, tenant_id, email, role, created_by | 7 years | None |
| `user.role.changed` | Role modification | user_id, old_role, new_role, changed_by | 7 years | None |
| `user.deactivated` | User deactivation | user_id, deactivated_by, reason | 7 years | None |
| `user.invitation.created` | Invitation sent | invitation_id, email, role, invited_by | 7 years | None |
| `user.invitation.accepted` | Invitation completed | invitation_id, user_id | 7 years | None |
| `user.invitation.expired` | Invitation expired unused | invitation_id, email | 7 years | None |
| `tenant.settings.changed` | Tenant settings modified | tenant_id, setting_key, old_value, new_value, changed_by | 7 years | Mask sensitive settings |
| `rbac.access.denied` | Permission check failed | user_id, role, resource, action | 7 years | None |

### Compliance Considerations

- **ATO Requirements**: Authentication logs must be retained for 7 years to support audit inquiries. Complete chain of custody for who accessed what and when.

- **Data Retention**: All authentication and authorization events retained for 7 years per constitution requirements. Archival to cold storage after 2 years.

- **Access Logging**:
  - Admin users can view audit logs for their tenant
  - System administrators (Clairo staff) can access audit logs for support with proper authorization
  - Audit log access itself is logged

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: New user registration and first login completes in under 60 seconds
- **SC-002**: JWT validation P95 latency is under 50ms
- **SC-003**: Zero cross-tenant data leakage incidents in penetration testing
- **SC-004**: 100% of authentication events are captured in audit logs
- **SC-005**: Role-based access control correctly enforces permissions in 100% of tested scenarios
- **SC-006**: System handles 100 concurrent logins without degradation
- **SC-007**: JWKS key rotation is transparent with zero authentication failures

### Validation Gates

Before marking this spec complete:
1. [ ] All P1 and P2 user stories have passing integration tests
2. [ ] RLS policies verified via direct database testing
3. [ ] Security review completed for JWT handling
4. [ ] Audit event coverage verified via integration tests
5. [ ] Load testing confirms performance requirements met
6. [ ] Penetration test confirms tenant isolation

---

## Technical Notes

### Clerk Integration

Clerk handles:
- User registration and password management
- Email verification
- MFA (TOTP authenticator apps)
- Session management
- JWKS key rotation

Clairo handles:
- JWT validation in backend
- Tenant association and management
- Role management (synced to Clerk custom claims)
- User-tenant relationship
- Invitation workflow

### PostgreSQL RLS Implementation

```sql
-- Enable RLS on tenant-scoped tables
ALTER TABLE clients ENABLE ROW LEVEL SECURITY;

-- Policy for tenant isolation
CREATE POLICY tenant_isolation ON clients
    USING (tenant_id = current_setting('app.current_tenant_id')::uuid);

-- Set context in middleware
SET app.current_tenant_id = 'tenant-uuid-here';
```

### Dependencies

**Depends on:**
- Spec 001 (Project Scaffolding) - COMPLETE

**Required for:**
- All subsequent specs (003+)

---

## Out of Scope

1. Business owner portal authentication (magic links) - covered in Spec 013
2. API key authentication for external integrations - future spec
3. SSO/SAML for enterprise practices - future consideration
4. Social login providers - not planned
5. Password policy configuration - handled by Clerk defaults
6. User profile management UI - basic implementation only

---

## Open Questions

1. **Clerk Plan Selection**: Which Clerk plan provides the features we need (custom claims, webhooks)? *Resolution needed before implementation.*

2. **Tenant Provisioning**: Should tenant creation be self-service or require admin approval? *Current assumption: Self-service for pilot.*

3. **Role Granularity**: Are three roles (Admin, Accountant, Staff) sufficient, or do we need more granular permissions? *Current assumption: Three roles sufficient for R1.*

---

## References

- [Constitution - Section IV: Multi-Tenancy](/.specify/memory/constitution.md)
- [Constitution - Section IX: Security Requirements](/.specify/memory/constitution.md)
- [Constitution - Section X: Auditing & Compliance](/.specify/memory/constitution.md)
- [Clerk Documentation](https://clerk.com/docs)
- [PostgreSQL RLS Documentation](https://www.postgresql.org/docs/current/ddl-rowsecurity.html)
