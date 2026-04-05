# Feature Specification: Infra & Launch Polish

**Feature Branch**: `045-infra-launch-polish`
**Created**: 2026-04-06
**Status**: Draft
**Input**: User description: "Spec 055 — Infra & Launch Polish: production deployment, monitoring, security hardening, CI/CD, domain setup"

## Assumptions

- Backend hosting: Fly.io (Docker-native, Sydney region, free tier for beta)
- Database: Fly Postgres or Supabase (managed, Sydney region)
- Redis: Upstash (serverless, free tier sufficient for beta)
- Object storage: Cloudflare R2 (S3-compatible, no egress fees)
- Frontend: Vercel (free tier, auto-deploys from GitHub)
- Secrets: hosted platform secret management (Fly secrets, Vercel env vars) — no external vault needed for beta
- No staging environment for initial beta — production only
- Stripe starts in test mode; live mode activation is a manual step by the founder
- ~10 beta tenants, no autoscaling needed

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Production Deployment: The App Is Live (Priority: P1)

As the founder, I deploy the entire Clairo platform to production so that beta users can sign up, connect Xero, and use the platform from clairo.com.au without any local infrastructure.

**Why this priority**: Nothing else matters until the app is accessible on the internet. Every other story depends on this.

**Independent Test**: Visit https://clairo.com.au in a browser, verify the landing page loads, sign up with Clerk, complete onboarding, and see the dashboard.

**Acceptance Scenarios**:

1. **Given** the code is merged to main, **When** deployment is triggered, **Then** the frontend is live at clairo.com.au and the backend API responds at api.clairo.com.au/health within 5 minutes
2. **Given** a new user visits clairo.com.au, **When** they click "Get Started", **Then** Clerk sign-up loads with production keys (not development mode banner)
3. **Given** a signed-up user, **When** they complete onboarding and reach the dashboard, **Then** all API calls succeed against the production backend
4. **Given** the backend is deployed, **When** Alembic migrations are run, **Then** the production database schema matches the latest state with RLS policies active
5. **Given** the Celery worker is deployed, **When** a Xero sync is triggered, **Then** the background task executes and completes successfully

---

### User Story 2 — Domain & SSL: Professional Web Presence (Priority: P1)

As a beta user, I access Clairo at clairo.com.au (not a random hosting subdomain), with HTTPS enforced, giving me confidence the platform is legitimate and my data is secure.

**Why this priority**: A custom domain with SSL is table stakes for a paid SaaS product handling financial data. Without it, no accountant will trust the platform.

**Independent Test**: Navigate to http://clairo.com.au and verify it redirects to https://clairo.com.au. Navigate to https://api.clairo.com.au/health and verify valid SSL certificate.

**Acceptance Scenarios**:

1. **Given** DNS is configured, **When** a user visits clairo.com.au, **Then** the frontend loads with a valid SSL certificate
2. **Given** DNS is configured, **When** the frontend calls api.clairo.com.au, **Then** API requests complete successfully with HTTPS
3. **Given** a user visits http://clairo.com.au (no HTTPS), **When** the page loads, **Then** they are automatically redirected to the HTTPS version
4. **Given** email is configured, **When** the system sends an email from noreply@clairo.com.au, **Then** the email is delivered (Resend domain verified)

---

### User Story 3 — CI/CD: Automated Quality Gates (Priority: P2)

As the developer, when I push code to GitHub, automated checks run (lint, tests, type-check) and the app deploys automatically on merge to main — with no manual SSH, Docker builds, or deployment scripts.

**Why this priority**: Manual deployments are error-prone and slow. CI/CD enables rapid iteration during beta without fear of breaking production.

**Independent Test**: Open a PR on GitHub, verify checks run automatically. Merge the PR, verify production updates within 10 minutes.

**Acceptance Scenarios**:

1. **Given** a developer opens a pull request, **When** CI runs, **Then** backend lint (ruff), backend tests (pytest), frontend lint (eslint), and frontend type-check (tsc) all execute
2. **Given** CI checks fail, **When** the developer views the PR, **Then** they see which specific check failed with clear error output
3. **Given** a PR is merged to main, **When** the merge completes, **Then** the frontend deploys to Vercel and the backend deploys to the hosting platform within 10 minutes
4. **Given** a deployment fails, **When** the developer checks the deployment status, **Then** they see the error and the previous working version remains live (rollback)

---

### User Story 4 — Monitoring & Error Tracking (Priority: P2)

As the developer, when a production error occurs, I receive an alert and can see the full error context (stack trace, user, request) so I can diagnose and fix issues quickly — without asking users to describe what happened.

**Why this priority**: During beta, rapid bug identification is critical. Sentry provides this without building custom monitoring.

**Independent Test**: Trigger a deliberate error in production (e.g., visit a URL that causes a server error), verify a Sentry alert appears within 1 minute with full context.

**Acceptance Scenarios**:

1. **Given** Sentry is configured, **When** an unhandled exception occurs in the backend, **Then** a Sentry event is created with stack trace, request context, and user info within 1 minute
2. **Given** Sentry is configured, **When** a frontend JavaScript error occurs, **Then** a Sentry event is created with component stack, breadcrumbs, and user session within 1 minute
3. **Given** a health check endpoint exists, **When** an uptime monitor pings it every 5 minutes, **Then** the developer is alerted if the service is down for more than 10 minutes

---

### User Story 5 — Security Hardening (Priority: P2)

As a beta user handling sensitive financial data, the platform protects my information through proper access controls, encrypted connections, and rate limiting — meeting the baseline security expectations for a financial services platform.

**Why this priority**: Accountants handle sensitive BAS data and bank transactions. Security failures would immediately destroy trust and potentially breach privacy obligations.

**Independent Test**: Run a basic security scan (e.g., check CORS headers, CSP headers, rate limiting) against the production API and frontend.

**Acceptance Scenarios**:

1. **Given** the production backend, **When** a request arrives from an unauthorized origin, **Then** CORS blocks the request (only clairo.com.au and api.clairo.com.au allowed)
2. **Given** the production database, **When** the application connects, **Then** it uses a non-superuser role so Row-Level Security policies are enforced
3. **Given** the auth endpoints, **When** more than 20 requests arrive from the same IP within 1 minute, **Then** the system returns 429 Too Many Requests
4. **Given** the frontend in production, **When** the page loads, **Then** Content Security Policy headers are present restricting script sources
5. **Given** all environment secrets, **When** the application runs, **Then** no secrets are exposed in logs, error messages, or client-side code

---

### User Story 6 — Service Credentials: Production Keys (Priority: P1)

As the founder preparing for beta launch, I switch all external service integrations from development/sandbox to production keys so that real payments are processed, real emails are sent, and real authentication works.

**Why this priority**: The app literally cannot function with development keys in production. Clerk shows "Development mode" banners, Stripe doesn't process real payments, etc.

**Independent Test**: Sign up on clairo.com.au with a real email, verify no "Development mode" warnings appear, start a trial, verify Stripe creates a real trial subscription.

**Acceptance Scenarios**:

1. **Given** production Clerk keys, **When** a user signs up, **Then** no "Development mode" banner appears and the user is created in the production Clerk instance
2. **Given** production Stripe keys, **When** a user starts a trial, **Then** a real Stripe subscription is created in live mode
3. **Given** the Stripe webhook endpoint registered, **When** Stripe sends a webhook event, **Then** the production backend processes it and updates subscription status
4. **Given** production Resend keys with verified clairo.com.au domain, **When** the system sends an email, **Then** it is delivered from noreply@clairo.com.au
5. **Given** production API keys for Anthropic, Voyage, and Pinecone, **When** AI features are used, **Then** they work without development/sandbox limitations

---

### Edge Cases

- What happens if the backend deployment fails mid-migration? The database migration should be run as a separate step before deploying the new code. If migration fails, the old code continues serving.
- What happens if Vercel deployment fails? Vercel keeps the previous deployment live. The developer sees the failure in the Vercel dashboard.
- What happens if the database connection pool is exhausted? The backend returns 503 Service Unavailable with a user-friendly message. Sentry captures the event.
- What happens if the Celery worker crashes? The hosting platform restarts it automatically. Tasks in the queue are retried.
- What happens if a secret is accidentally committed to git? The CI pipeline should fail if .env files are detected in the commit. Production secrets are stored in platform secret management, never in code.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The frontend MUST be accessible at clairo.com.au with valid HTTPS
- **FR-002**: The backend API MUST be accessible at api.clairo.com.au with valid HTTPS
- **FR-003**: The system MUST automatically deploy when code is merged to the main branch
- **FR-004**: All code changes MUST pass automated lint and test checks before merge
- **FR-005**: The system MUST use production credentials for all external services (authentication, payments, email, AI)
- **FR-006**: The database MUST use a non-superuser role to ensure Row-Level Security policies are enforced
- **FR-007**: The system MUST report unhandled errors to a monitoring service within 1 minute
- **FR-008**: The backend API MUST enforce CORS restrictions allowing only the production domain
- **FR-009**: Authentication and webhook endpoints MUST enforce rate limiting (max 20 requests per minute per IP)
- **FR-010**: The system MUST serve all data from Australian data centers
- **FR-011**: No secrets (API keys, database credentials) MUST appear in client-side code, logs, or error responses
- **FR-012**: The backend MUST include a health check endpoint that returns service status for uptime monitoring
- **FR-013**: Background task workers MUST be deployed alongside the backend and auto-restart on failure
- **FR-014**: Database migrations MUST be runnable as a separate deployment step

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: Production Clerk instance handles auth — Clerk provides its own audit log
- [x] **Integration Events**: Stripe webhook registration, external service credential rotation

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| infra.deployment.completed | Code deployed to production | version, commit hash, deployer | 1 year | None |
| infra.secret.rotated | API key or credential changed | service name, rotation date | 7 years | Key value NEVER logged |
| infra.error.unhandled | Unhandled exception in production | stack trace, request context, user ID | 90 days (Sentry) | PII masked in breadcrumbs |

### Compliance Considerations

- **ATO Requirements**: All financial data must reside in Australian data centers (Sydney region)
- **Data Retention**: Production database backups retained per hosting provider policy (minimum 7 days for point-in-time recovery)
- **Access Logging**: Production infrastructure access limited to founder only during beta

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: The platform is accessible at clairo.com.au with 99.5% uptime during the first month of beta
- **SC-002**: A new user can sign up, complete onboarding, and reach the dashboard in under 5 minutes
- **SC-003**: Code merged to main is live in production within 10 minutes
- **SC-004**: 100% of unhandled errors are captured by the monitoring system with full context
- **SC-005**: All API responses from the production backend are served over HTTPS with valid certificates
- **SC-006**: The monthly infrastructure cost for ~10 beta tenants is under $100 AUD
- **SC-007**: No production secrets are exposed in client-side code, build artifacts, or error messages
- **SC-008**: The production database enforces Row-Level Security (non-superuser connection role verified)
