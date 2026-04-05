# Research: Infra & Launch Polish

**Date**: 2026-04-06

## R1: Backend Hosting Platform

**Decision**: Fly.io (Sydney region `syd`)

**Rationale**: Fly.io is the only budget-friendly platform with a real Sydney region for Australian data residency. Docker-native deployment, ~$15 USD/month for API + Celery worker + self-managed Postgres. The existing `deploy-production.yml` workflow references Railway but needs to be updated to Fly.io — Railway has no Sydney region.

**Estimated costs**: API machine ($7/mo) + Celery worker ($3/mo) + Postgres on volume ($2/mo) = ~$12-15 USD/month (~$23 AUD)

**Alternatives rejected**:
- Railway: No Sydney region — only US/EU. Disqualified for AU data residency.
- Render: No Sydney region. Disqualified.
- AWS ECS/Fargate: Overkill for beta, complex to set up for solo developer

## R2: Managed PostgreSQL

**Decision**: Railway Postgres or Supabase (founder's choice)

**Rationale**: Railway offers integrated Postgres within the same project (simplest). Supabase offers a free tier with more tooling (dashboard, auth, etc.) but adds another service to manage. For beta with ~10 tenants, either works.

**Key requirement**: The connection must use a non-superuser role so RLS policies are enforced. Both platforms support creating additional database roles.

## R3: Managed Redis

**Decision**: Upstash (serverless Redis)

**Rationale**: Celery needs Redis for task queue and result backend. Upstash offers serverless Redis with a free tier (10,000 commands/day) which is sufficient for beta. Railway also offers Redis as an add-on. Either works — Upstash has the advantage of no idle costs.

## R4: Object Storage (replacing MinIO)

**Decision**: Cloudflare R2

**Rationale**: S3-compatible API (MinIO code works without changes), no egress fees, generous free tier (10GB storage, 10M requests/month). The backend's MinIO client configuration just needs endpoint/credentials swapped.

## R5: Rate Limiting Approach

**Decision**: In-process rate limiting using slowapi (FastAPI middleware)

**Rationale**: For beta with ~10 tenants, in-process rate limiting is sufficient. No need for Redis-based distributed rate limiting yet. slowapi wraps the standard limits library and integrates with FastAPI.

**Configuration**:
- Auth endpoints (login, register): 20 req/min per IP
- Webhook endpoints: 100 req/min per IP (Stripe sends bursts)
- General API: no rate limit (auth required anyway)

**Alternative**: Cloudflare or Railway proxy-level rate limiting — more robust but harder to customize and debug.

## R6: Content Security Policy

**Decision**: Add CSP header to vercel.json with allowlisted domains

**Rationale**: CSP prevents XSS by restricting script/style/image sources. For Clairo, we need to allow: Clerk (auth widget), PostHog (analytics), Sentry (error tracking), Stripe (payment), and self.

**CSP directives**:
```
default-src 'self';
script-src 'self' 'unsafe-inline' 'unsafe-eval' https://*.clerk.accounts.dev https://js.stripe.com https://*.posthog.com;
style-src 'self' 'unsafe-inline';
img-src 'self' data: https://*.clerk.com https://img.clerk.com https://www.clairo.com.au;
connect-src 'self' https://*.clerk.accounts.dev https://api.stripe.com https://*.posthog.com https://*.sentry.io https://api.clairo.com.au;
frame-src https://js.stripe.com https://*.clerk.accounts.dev;
font-src 'self' data:;
```

## R7: Production Database Role

**Decision**: Create `clairo_app` role with limited privileges

**Rationale**: The superuser bypasses RLS policies. The production app must connect as a non-superuser so that `tenant_id` isolation is enforced at the database level. This is a critical security requirement.

**SQL script**:
```sql
CREATE ROLE clairo_app WITH LOGIN PASSWORD 'secure_password';
GRANT CONNECT ON DATABASE clairo TO clairo_app;
GRANT USAGE ON SCHEMA public TO clairo_app;
GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO clairo_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO clairo_app;
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA public TO clairo_app;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT USAGE, SELECT ON SEQUENCES TO clairo_app;
-- DO NOT grant SUPERUSER or BYPASSRLS
```

## R8: Existing Infrastructure Assessment

**Decision**: Infrastructure is 80% built. Focus on provisioning and verification, not building.

**What already exists** (confirmed by code review):
- Production Dockerfiles (backend, worker, beat) — all multi-stage, non-root user
- Vercel config with syd1 region and security headers
- GitHub Actions CI (lint, test, type-check, build)
- GitHub Actions deploy workflow (Railway + Vercel)
- Sentry SDK integration with all major integrations
- Health check endpoint at /health
- CORS settings configurable via env vars
- PostHog analytics gated behind cookie consent

**What needs to be created (code)**:
- Rate limiting middleware (~50 lines)
- CSP header in vercel.json (~5 lines)
- Production DB role SQL script (~10 lines)
- Production env var template
- Production checklist document
