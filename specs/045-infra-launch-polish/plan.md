# Implementation Plan: Infra & Launch Polish

**Branch**: `045-infra-launch-polish` | **Date**: 2026-04-06 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/045-infra-launch-polish/spec.md`

## Summary

Deploy Clairo to production for beta launch. The infrastructure is 80% built (Dockerfiles, CI/CD workflows, Vercel config, Sentry integration all exist). The remaining work is: (1) provision production services, (2) configure DNS and domain, (3) set production secrets, (4) add rate limiting, (5) create production database role, (6) verify end-to-end deployment.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, gunicorn, Celery, Docker, GitHub Actions, Vercel CLI
**Storage**: PostgreSQL 16 (managed), Redis (managed), S3-compatible object storage
**Testing**: GitHub Actions CI (backend: ruff + pytest, frontend: eslint + tsc)
**Target Platform**: Linux containers (backend), Vercel edge network (frontend)
**Performance Goals**: Health check <1s, page load <3s, deployment <10min
**Constraints**: Sydney region (AU data residency), <$100 AUD/month, single developer
**Scale/Scope**: ~10 beta tenants

## What Already Exists

| Component | Status | File(s) |
|-----------|--------|---------|
| Backend Dockerfile (prod) | DONE | `backend/Dockerfile.prod` — multi-stage, gunicorn, auto-migrations |
| Worker Dockerfile (prod) | DONE | `infrastructure/docker/Dockerfile.worker` — Celery worker |
| Beat Dockerfile (prod) | DONE | `infrastructure/docker/Dockerfile.beat` — Celery beat |
| Vercel config | DONE | `frontend/vercel.json` — syd1 region, security headers, redirects |
| CI pipeline | DONE | `.github/workflows/ci.yml` — backend lint+test, frontend lint+build |
| Deploy workflow | NEEDS UPDATE | `.github/workflows/deploy-production.yml` — currently targets Railway, needs Fly.io |
| Sentry integration | DONE | `backend/app/main.py` — init_sentry() with FastAPI/Celery/Redis/SQLAlchemy integrations |
| Sentry config | DONE | `backend/app/config.py` — SentrySettings with env prefix SENTRY_ |
| Health endpoint | DONE | `GET /health` returns status, version, environment |
| CORS config | DONE | `backend/app/config.py` — CorsSettings with env prefix CORS_ |
| Security headers | DONE | `frontend/vercel.json` — X-Content-Type-Options, X-Frame-Options, Referrer-Policy |

## What Needs To Be Done

| Task | Category | Effort |
|------|----------|--------|
| Provision Fly.io backend (Sydney region) | Manual (flyctl CLI) | 30min |
| Provision managed PostgreSQL | Manual (dashboard) | 15min |
| Provision Upstash Redis | Manual (dashboard) | 10min |
| Provision Cloudflare R2 storage | Manual (dashboard) | 10min |
| Configure DNS (clairo.com.au) | Manual (DNS registrar) | 15min |
| Set production secrets in Fly.io + Vercel | Manual (flyctl + dashboard) | 30min |
| Create production Clerk instance | Manual (Clerk dashboard) | 15min |
| Register Stripe webhook (live) | Manual (Stripe dashboard) | 10min |
| Create non-superuser DB role | SQL script | 10min |
| Add rate limiting middleware | Code | 30min |
| Add CSP headers to vercel.json | Code | 10min |
| Configure Sentry DSN | Config | 5min |
| Configure uptime monitoring | Manual (Uptime service) | 10min |
| Verify end-to-end deployment | Testing | 1hr |

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | No structural changes |
| Repository pattern | N/A | No new data access |
| Multi-tenancy (tenant_id) | PASS | Production DB role ensures RLS enforcement |
| Audit logging | PASS | No new audit events beyond deployment tracking |
| Security | PASS | Rate limiting + CSP + CORS + non-superuser role |

## Project Structure

### Infrastructure files to create/modify

```text
backend/
├── app/
│   └── core/
│       └── rate_limit.py          # NEW: rate limiting middleware
├── .env.production.example        # NEW: production env var template
└── scripts/
    └── create_production_role.sql # NEW: non-superuser DB role script

frontend/
└── vercel.json                    # MODIFY: add CSP header

.github/
└── workflows/
    └── deploy-production.yml      # VERIFY: secrets configured

infrastructure/
└── deployment/
    └── production-checklist.md    # NEW: manual provisioning checklist
```

## Implementation Phases

### Phase 1: Code Changes (rate limiting, CSP, DB role script)

1. Create rate limiting middleware for auth/webhook endpoints
2. Add Content-Security-Policy header to vercel.json
3. Create SQL script for production database role (non-superuser with RLS)
4. Create production env var template (.env.production.example)
5. Create production checklist document for manual provisioning steps

### Phase 2: Service Provisioning (manual, guided by checklist)

This phase is manual — the developer follows the production checklist:

1. Create Fly.io app → deploy backend Docker image → configure Sydney region (`syd`)
2. Provision Postgres on Fly volume (or Supabase) → run migration → create non-superuser role
3. Provision Upstash Redis → get connection URL
4. Provision Cloudflare R2 → create bucket → get credentials
5. Connect Vercel to GitHub repo → configure frontend project
6. Set all production env vars in Fly.io (`fly secrets set`) + Vercel dashboards

### Phase 3: Domain & DNS

1. Add clairo.com.au to Vercel → get DNS records
2. Add api.clairo.com.au CNAME → Railway domain
3. Verify SSL certificates auto-provision
4. Verify Resend domain (clairo.com.au) DNS records

### Phase 4: Production Credentials

1. Create production Clerk instance → get live keys
2. Activate Stripe live mode → get live keys → register webhook endpoint
3. Configure Sentry DSN in production env
4. Verify Anthropic, Voyage, Pinecone API keys work in production

### Phase 5: Verification & Launch

1. Push to main → verify CI passes → verify auto-deploy
2. Visit clairo.com.au → verify landing page loads
3. Sign up → complete onboarding → verify dashboard works
4. Trigger Xero sync → verify background task executes
5. Check Sentry → verify error tracking active
6. Run rate limit test → verify 429 responses
7. Verify RLS enforcement (connect as non-superuser, test cross-tenant query blocked)

## Complexity Tracking

No constitution violations. Most work is manual service provisioning, not code changes.
