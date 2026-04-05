# Tasks: Infra & Launch Polish

**Input**: Design documents from `/specs/045-infra-launch-polish/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested. Test tasks omitted.

**Organization**: Tasks grouped by user story. Mix of code tasks and manual provisioning tasks (marked with MANUAL).

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files/services, no dependencies)
- **[Story]**: Which user story this task belongs to
- **MANUAL**: Task requires manual action in a dashboard/CLI outside the codebase

---

## Phase 0: Git Setup

- [ ] T000 Checkout the feature branch
  - Run: `git checkout 045-infra-launch-polish` (branch already exists)
  - Verify: You are on the `045-infra-launch-polish` branch

---

## Phase 1: Setup (Code Changes)

**Purpose**: All code changes needed before production deployment. These are the only tasks that modify the codebase.

- [ ] T001 Create rate limiting middleware at `backend/app/core/rate_limit.py` — use slowapi library. Configure: auth endpoints (`/api/v1/auth/*`) at 20 req/min per IP, webhook endpoints (`/api/v1/billing/webhooks/*`) at 100 req/min per IP. Add the limiter to the FastAPI app in `backend/app/main.py`
- [ ] T002 [P] Add Content-Security-Policy header to `frontend/vercel.json` — add CSP directive allowing: self, Clerk (`*.clerk.accounts.dev`, `*.clerk.com`), Stripe (`js.stripe.com`, `api.stripe.com`), PostHog (`*.posthog.com`), Sentry (`*.sentry.io`), and clairo.com.au. Allow `unsafe-inline` for styles and `unsafe-eval` for Next.js
- [ ] T003 [P] Create production database role SQL script at `backend/scripts/create_production_role.sql` — create `clairo_app` role with SELECT/INSERT/UPDATE/DELETE on all tables, USAGE on sequences, NO superuser, NO bypassrls. Include comments explaining RLS enforcement
- [ ] T004 [P] Create production env var template at `backend/.env.production.example` — list all required env vars from `contracts/infrastructure.md` with placeholder values and comments. Mark which are backend-only vs frontend (Vercel)
- [ ] T005 [P] Update deploy workflow at `.github/workflows/deploy-production.yml` — replace Railway references with Fly.io. Use `flyctl deploy` for backend, keep Vercel CLI for frontend. Add `FLY_API_TOKEN` secret reference. Update health check URL to use `PRODUCTION_BACKEND_URL` secret
- [ ] T006 [P] Create Fly.io config at `fly.toml` in project root — configure app name (`clairo-api`), region (`syd`), port 8000, health check at `/health`, min 1 machine, auto-stop disabled. Reference `backend/Dockerfile.prod`
- [ ] T007 [P] Create production checklist at `infrastructure/deployment/production-checklist.md` — step-by-step guide for provisioning Fly.io, Postgres, Upstash Redis, Cloudflare R2, Vercel, DNS, and all production credentials. Based on `quickstart.md` content

**Checkpoint**: All code changes ready. No provisioning done yet.

---

## Phase 2: Foundational (Service Provisioning)

**Purpose**: Provision production infrastructure. MANUAL tasks — developer follows the checklist.

**CRITICAL**: Must complete before any user story can be verified in production.

- [ ] T008 MANUAL — Provision Fly.io app in Sydney region using `flyctl launch` with `fly.toml` config. Deploy backend using `flyctl deploy`. Verify health check at the Fly.io-assigned URL
- [ ] T009 MANUAL — Provision PostgreSQL (Fly Postgres or Supabase, Sydney region). Run `alembic upgrade head` as superuser. Then run `scripts/create_production_role.sql` to create `clairo_app` role. Update `DATABASE_URL` to use `clairo_app`
- [ ] T010 [P] MANUAL — Provision Upstash Redis at https://upstash.com. Create database in ap-southeast region. Copy connection URL. Set as `REDIS_URL` and `CELERY_BROKER_URL` in Fly.io secrets
- [ ] T011 [P] MANUAL — Provision Cloudflare R2 bucket at Cloudflare dashboard. Create API token with R2 read/write. Set `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_USE_SSL=true` in Fly.io secrets
- [ ] T012 MANUAL — Deploy Celery worker on Fly.io — create second app (`clairo-worker`) using `infrastructure/docker/Dockerfile.worker`, same secrets as backend, Sydney region. Verify worker starts and connects to Redis

**Checkpoint**: Backend API, database, Redis, storage, and worker all running in production.

---

## Phase 3: User Story 1 — Production Deployment (Priority: P1) — MVP

**Goal**: The app is live and accessible at a URL (even if not custom domain yet)

**Independent Test**: Visit the Fly.io URL, verify `/health` returns healthy. Visit Vercel preview URL, verify landing page loads.

- [ ] T013 [US1] MANUAL — Deploy frontend to Vercel. Import GitHub repo, set root directory to `frontend`, configure all `NEXT_PUBLIC_*` env vars. Verify preview deployment loads landing page
- [ ] T014 [US1] MANUAL — Set all backend production env vars in Fly.io using `fly secrets set`. Reference `contracts/infrastructure.md` for the full list. Verify backend restarts and `/health` returns healthy
- [ ] T015 [US1] MANUAL — Verify end-to-end: visit Vercel preview URL → landing page loads → sign-up form appears (even with dev Clerk keys initially) → API calls to backend succeed

**Checkpoint**: App is live on hosting platform URLs (not custom domain yet).

---

## Phase 4: User Story 2 — Domain & SSL (Priority: P1)

**Goal**: clairo.com.au serves the frontend, api.clairo.com.au serves the backend, HTTPS enforced

**Independent Test**: Visit https://clairo.com.au and https://api.clairo.com.au/health — both load with valid SSL.

- [ ] T016 [US2] MANUAL — Add `clairo.com.au` and `www.clairo.com.au` as custom domains in Vercel dashboard. Copy the DNS records Vercel provides
- [ ] T017 [US2] MANUAL — Add `api.clairo.com.au` as custom domain in Fly.io using `fly certs create api.clairo.com.au`. Note the CNAME target
- [ ] T018 [US2] MANUAL — Configure DNS at domain registrar for clairo.com.au: add `www` CNAME → Vercel, apex A record → Vercel IP, `api` CNAME → Fly.io domain. Wait for propagation
- [ ] T019 [US2] MANUAL — Verify SSL certificates auto-provisioned for all three domains. Test: `curl -I https://clairo.com.au`, `curl -I https://www.clairo.com.au`, `curl -I https://api.clairo.com.au/health`
- [ ] T020 [US2] MANUAL — Verify Resend domain DNS records for clairo.com.au are correctly configured. Send a test email from production to verify delivery

**Checkpoint**: Custom domain working with HTTPS, emails sending from clairo.com.au.

---

## Phase 5: User Story 6 — Production Keys (Priority: P1)

**Goal**: All external services using production/live credentials

**Independent Test**: Sign up on clairo.com.au — no "Development mode" banner, trial creates real Stripe subscription.

- [ ] T021 [US6] MANUAL — Create production Clerk instance at https://dashboard.clerk.com. Copy `sk_live_*`, `pk_live_*`, and JWKS URL. Update in both Fly.io secrets and Vercel env vars. Configure allowed origins to `clairo.com.au`
- [ ] T022 [US6] MANUAL — Activate Stripe live mode. Create live product + price ($299 AUD/month). Register webhook endpoint at `https://api.clairo.com.au/api/v1/billing/webhooks/stripe` with events: `customer.subscription.*`, `invoice.paid`, `invoice.payment_failed`, `checkout.session.completed`. Copy webhook secret. Update Fly.io secrets with live Stripe keys + webhook secret
- [ ] T023 [US6] MANUAL — Update Xero OAuth redirect URI to `https://www.clairo.com.au/settings/integrations/xero/callback` in Xero developer portal and Fly.io secrets
- [ ] T024 [US6] MANUAL — Verify all API keys work: Anthropic (AI features), Voyage (embeddings), Pinecone (vector search). Test by triggering an AI query in production
- [ ] T025 [US6] Verify end-to-end with production keys: sign up → no dev banner → complete onboarding → trial created in Stripe live → dashboard loads → email received from noreply@clairo.com.au

**Checkpoint**: All services running with production credentials. Real signups work.

---

## Phase 6: User Story 3 — CI/CD (Priority: P2)

**Goal**: Code changes auto-deploy to production on merge to main

**Independent Test**: Open a test PR, verify CI runs. Merge it, verify production updates within 10 minutes.

- [ ] T026 [US3] MANUAL — Add `FLY_API_TOKEN` to GitHub repository secrets (generate at https://fly.io/user/personal_access_tokens)
- [ ] T027 [US3] MANUAL — Add Vercel secrets to GitHub: `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`
- [ ] T028 [US3] MANUAL — Test CI pipeline: create a test PR with a minor change, verify all 4 CI jobs pass (backend-test, backend-lint, frontend-lint, frontend-build)
- [ ] T029 [US3] MANUAL — Test deploy pipeline: merge the test PR to main, verify Fly.io backend deploys and Vercel frontend deploys within 10 minutes. Verify health check passes

**Checkpoint**: CI/CD pipeline working end-to-end.

---

## Phase 7: User Story 4 — Monitoring (Priority: P2)

**Goal**: Production errors captured by Sentry, uptime monitored

**Independent Test**: Trigger a deliberate error in production, verify Sentry alert appears.

- [ ] T030 [US4] MANUAL — Create Sentry project at https://sentry.io. Get DSN. Set `SENTRY_DSN` and `SENTRY_ENVIRONMENT=production` in both Fly.io secrets and Vercel env vars
- [ ] T031 [US4] MANUAL — Verify Sentry captures backend errors: trigger a deliberate 500 error (e.g., invalid API call), check Sentry dashboard for the event with stack trace and request context
- [ ] T032 [US4] MANUAL — Set up uptime monitoring: use BetterStack (free tier), Uptime Robot, or similar. Configure ping to `https://api.clairo.com.au/health` every 5 minutes. Set up email alert for downtime

**Checkpoint**: Errors captured in Sentry, uptime alerts configured.

---

## Phase 8: User Story 5 — Security Hardening (Priority: P2)

**Goal**: CORS restricted, rate limiting active, RLS enforced, CSP headers present

**Independent Test**: Test CORS from unauthorized origin (blocked), test rate limiting (429 after threshold), verify CSP header in response.

- [ ] T033 [US5] Set production CORS origins in Fly.io secrets: `CORS_ORIGINS=https://www.clairo.com.au,https://clairo.com.au` — verify API rejects requests from other origins
- [ ] T034 [US5] Verify rate limiting works in production: send 25 rapid requests to `/api/v1/auth/register` from the same IP, verify the 21st returns 429 Too Many Requests
- [ ] T035 [US5] Verify RLS enforcement: connect to production database as `clairo_app` role, attempt to query across tenants, verify RLS blocks cross-tenant data access
- [ ] T036 [US5] Verify CSP header in production: `curl -I https://clairo.com.au` — confirm `Content-Security-Policy` header is present in the response

**Checkpoint**: Security hardening verified in production.

---

## Phase 9: Polish & Cross-Cutting

- [ ] T037 [P] Run backend lint on changed files — `cd backend && uv run ruff check app/core/rate_limit.py app/main.py`
- [ ] T038 [P] Run frontend type-check — `cd frontend && npx tsc --noEmit`
- [ ] T039 Update `HANDOFF.md` — mark Spec 055 (Infra & Launch Polish) as DONE in the launch checklist

---

## Phase FINAL: PR & Merge

- [ ] T040 Run full validation suite
  - Run: `cd backend && uv run ruff check . && uv run pytest`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`

- [ ] T041 Commit all code changes and push
  - Stage: rate_limit.py, fly.toml, vercel.json, deploy-production.yml, create_production_role.sql, .env.production.example, production-checklist.md
  - Commit with descriptive message
  - Push to remote

- [ ] T042 Merge to main (triggers production deployment)

- [ ] T043 Update ROADMAP.md
  - Mark Spec 055 as COMPLETE
  - Update status: BETA LAUNCH READY

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0** (Git): First
- **Phase 1** (Code): After Phase 0 — all code changes
- **Phase 2** (Provisioning): After Phase 1 — service setup
- **Phase 3** (US1 Deployment): After Phase 2 — app goes live
- **Phase 4** (US2 Domain): After Phase 3 — custom domain
- **Phase 5** (US6 Prod Keys): After Phase 4 — switch to live credentials
- **Phase 6** (US3 CI/CD): After Phase 3 — can parallel with US2
- **Phase 7** (US4 Monitoring): After Phase 3 — can parallel with US2
- **Phase 8** (US5 Security): After Phase 1 code + Phase 3 deployment
- **Phase 9** (Polish): After all user stories
- **Phase FINAL**: After Phase 9

### Critical Path

```
Code changes → Provision services → Deploy app → Custom domain → Production keys → LAUNCH
                                        ↓
                                   CI/CD (parallel)
                                   Monitoring (parallel)
                                   Security (parallel)
```

### Parallel Opportunities

- Phase 1: T002-T007 are all independent files, can run in parallel
- Phase 2: T010 + T011 (Redis + R2) can parallel
- Phase 6-8: CI/CD, Monitoring, Security can all run in parallel after deployment

---

## Implementation Strategy

### MVP First (US1 Only — App Is Live)

1. Phase 1: Code changes (rate limiting, CSP, fly.toml, DB role script)
2. Phase 2: Provision services (Fly.io, Postgres, Redis, R2)
3. Phase 3: Deploy and verify (US1)
4. **STOP and VALIDATE**: App accessible at Fly.io/Vercel URLs
5. This is a deployable MVP — the app works on hosting platform URLs

### Full Launch

6. Phase 4: Custom domain (clairo.com.au)
7. Phase 5: Production credentials (Clerk live, Stripe live)
8. Phases 6-8: CI/CD, Monitoring, Security (parallel)
9. Phase 9 + FINAL: Polish and merge

---

## Estimated Cost (Monthly)

| Service | Cost (USD) | Cost (AUD ~1.55) |
|---------|-----------|-------------------|
| Fly.io (API + Worker + Postgres) | ~$15 | ~$23 |
| Upstash Redis | $0 (free tier) | $0 |
| Cloudflare R2 | $0 (free tier) | $0 |
| Vercel (hobby/pro) | $0-20 | $0-31 |
| Sentry (free tier) | $0 | $0 |
| BetterStack uptime (free tier) | $0 | $0 |
| **Total** | **$15-35** | **$23-54** |

---

## Notes

- 43 tasks total across 11 phases
- ~7 code tasks (Phase 1), ~36 manual/verification tasks
- MVP scope: 15 tasks (Phase 0-3) to get app live on hosting URLs
- Most effort is manual provisioning, not coding
- `fly.toml` in project root is the key new config file for Fly.io deployment
- The deploy workflow needs updating from Railway → Fly.io
- slowapi dependency needed for rate limiting: add to `pyproject.toml`
