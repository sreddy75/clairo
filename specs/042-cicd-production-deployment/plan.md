# Implementation Plan: CI/CD Pipeline & Production Deployment

**Branch**: `042-cicd-production-deployment` | **Date**: 2026-01-04 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/042-cicd-production-deployment/spec.md`

## Summary

Implement a complete CI/CD pipeline using GitHub Actions that enables rapid, safe deployment of code changes to beta testers. The system automates testing (backend pytest/ruff/mypy, frontend eslint/typescript), provides preview deployments for PRs, and handles production deployments to Railway (backend) and Vercel (frontend). Database migrations are automated via Alembic, secrets are managed through platform-native solutions, and health checks ensure deployment reliability.

## Technical Context

**Language/Version**: YAML (GitHub Actions), Python 3.12 (backend testing), TypeScript 5.x (frontend testing)
**Primary Dependencies**: GitHub Actions, Railway CLI, Vercel CLI, Docker
**Storage**: N/A (CI/CD pipeline - no application data storage)
**Testing**: pytest + ruff + mypy (backend), eslint + tsc (frontend)
**Target Platform**: GitHub Actions runners (Ubuntu latest), Railway (backend hosting), Vercel (frontend hosting)
**Project Type**: web (existing backend + frontend structure)
**Performance Goals**: Deployment completes within 15 minutes, PR checks complete within 10 minutes
**Constraints**: Zero downtime deployments, secrets never exposed in logs, Australian data residency for production
**Scale/Scope**: Small team (<10 devs), moderate PR volume (<20 PRs/week), 3 environments (preview, staging, production)

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular Monolith | PASS | CI/CD is infrastructure, doesn't affect app architecture |
| Technology Stack | PASS | Uses approved stack (Python, TypeScript, Docker) |
| Repository Pattern | N/A | CI/CD doesn't add database access |
| Multi-Tenancy | N/A | CI/CD operates at infrastructure level |
| Testing Strategy | PASS | CI/CD enforces existing test requirements |
| Code Quality | PASS | CI/CD enforces linting/formatting |
| API Design | N/A | No new APIs added |
| Security | PASS | Uses platform-native secrets (GitHub Secrets, Railway/Vercel env vars) |
| Auditing | PASS | Deployment events tracked via platform logs |
| AI/RAG Standards | N/A | No AI components |

**Gate Status**: ALL GATES PASS - Proceed with Phase 0

## Project Structure

### Documentation (this feature)

```text
specs/042-cicd-production-deployment/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # N/A - no data models (infrastructure feature)
├── quickstart.md        # Phase 1 output - deployment guide
├── contracts/           # N/A - no API contracts
└── tasks.md             # Phase 2 output
```

### Source Code (repository root)

```text
# CI/CD Configuration (NEW)
.github/
├── workflows/
│   ├── ci.yml                    # PR checks (test, lint, typecheck)
│   ├── deploy-staging.yml        # Staging deployment (develop branch)
│   ├── deploy-production.yml     # Production deployment (main branch)
│   └── preview.yml               # Preview environments for PRs
├── actions/
│   └── setup-backend/            # Reusable action for Python setup
│       └── action.yml
└── CODEOWNERS                    # Code ownership for reviews

# Production Dockerfiles (NEW/MODIFIED)
backend/
├── Dockerfile.prod               # Multi-stage production build
├── docker-compose.prod.yml       # Production compose override
└── .dockerignore                 # Docker build exclusions

# Infrastructure Configuration (NEW/MODIFIED)
infrastructure/
├── docker/
│   ├── Dockerfile.backend        # Production backend image
│   ├── Dockerfile.worker         # Production Celery worker image
│   └── Dockerfile.beat           # Production Celery beat image
└── deployment/
    ├── railway.toml              # Railway configuration
    ├── vercel.json               # Vercel configuration
    └── env.template              # Environment variable template

# Environment Templates (NEW)
.env.production.template          # Production env vars (no secrets)
.env.staging.template             # Staging env vars (no secrets)

# Health Check Endpoints (EXISTING - verify/enhance)
backend/app/api/health.py         # Health check endpoint
```

**Structure Decision**: This feature adds infrastructure configuration files at the repository root level (`.github/`, `infrastructure/`) and production Docker configurations. No changes to the existing backend/frontend application code structure.

## Complexity Tracking

No constitution violations requiring justification.

---

## Phase 0: Research Tasks

### Research Areas

1. **GitHub Actions Best Practices for Python + Next.js Monorepo**
   - Optimal caching strategies for uv (Python) and npm
   - Parallel job execution for faster CI
   - Reusable workflows vs composite actions

2. **Railway Deployment Patterns**
   - Multi-service deployment (API, Worker, Beat)
   - Database migration handling
   - Health check configuration
   - Zero-downtime deployment strategy

3. **Vercel Deployment with GitHub Actions**
   - Preview deployments for PRs
   - Production deployment triggers
   - Environment variable management
   - Build caching optimization

4. **Secrets Management Best Practices**
   - GitHub Secrets organization
   - Environment-specific secrets
   - Secret rotation strategies
   - Audit logging for secret access

5. **Database Migration in CI/CD**
   - Alembic migration in deployment pipeline
   - Migration failure handling
   - Rollback strategies for migrations

---

## Phase 1: Design Artifacts

### Artifacts to Generate

1. **research.md** - Consolidated research findings
2. **quickstart.md** - Developer guide for CI/CD usage
3. **No data-model.md** - Infrastructure feature, no application data models
4. **No contracts/** - Infrastructure feature, no new APIs

---

## Deployment Architecture

```text
┌─────────────────────────────────────────────────────────────────────────────┐
│                           GITHUB REPOSITORY                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Pull Request ──────► CI Workflow ─────► Tests Pass? ─────► Preview Deploy │
│       │                   │                   │                    │        │
│       │                   ▼                   │                    ▼        │
│       │              ┌─────────┐              │            ┌─────────────┐  │
│       │              │ Backend │              │            │   Vercel    │  │
│       │              │ pytest  │              │            │  Preview    │  │
│       │              │ ruff    │              │            │   URL       │  │
│       │              │ mypy    │              │            └─────────────┘  │
│       │              └─────────┘              │                             │
│       │              ┌─────────┐              │                             │
│       │              │Frontend │              │                             │
│       │              │ eslint  │              │                             │
│       │              │ tsc     │              │                             │
│       │              └─────────┘              │                             │
│       │                                       │                             │
│       ▼                                       ▼                             │
│  Merge to develop ──────────────────────► Staging Deploy                    │
│       │                                       │                             │
│       │                                       ▼                             │
│       │                              ┌─────────────────┐                    │
│       │                              │    RAILWAY      │                    │
│       │                              │   (Staging)     │                    │
│       │                              │ ┌─────────────┐ │                    │
│       │                              │ │   Backend   │ │                    │
│       │                              │ │   Worker    │ │                    │
│       │                              │ │    Beat     │ │                    │
│       │                              │ │  PostgreSQL │ │                    │
│       │                              │ │   Redis     │ │                    │
│       │                              │ └─────────────┘ │                    │
│       │                              └─────────────────┘                    │
│       │                              ┌─────────────────┐                    │
│       │                              │    VERCEL       │                    │
│       │                              │   (Staging)     │                    │
│       │                              └─────────────────┘                    │
│       │                                                                     │
│       ▼                                                                     │
│  Merge to main ─────────────────────► Production Deploy                     │
│                                           │                                 │
│                                           ▼                                 │
│                                  ┌─────────────────┐                        │
│                                  │    RAILWAY      │                        │
│                                  │  (Production)   │                        │
│                                  │ ┌─────────────┐ │                        │
│                                  │ │   Backend   │ │                        │
│                                  │ │   Worker    │ │                        │
│                                  │ │    Beat     │ │                        │
│                                  │ │  PostgreSQL │ │                        │
│                                  │ │   Redis     │ │                        │
│                                  │ └─────────────┘ │                        │
│                                  └─────────────────┘                        │
│                                  ┌─────────────────┐                        │
│                                  │    VERCEL       │                        │
│                                  │  (Production)   │                        │
│                                  └─────────────────┘                        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## GitHub Actions Workflow Structure

### Workflow Files

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `ci.yml` | Pull requests to main/develop | Run tests, linting, type checks |
| `preview.yml` | Pull requests to main | Deploy preview to Vercel |
| `deploy-staging.yml` | Push to develop | Deploy to staging environment |
| `deploy-production.yml` | Push to main | Deploy to production environment |

### Job Structure

```yaml
# ci.yml structure
jobs:
  backend-test:
    - Setup Python + uv
    - Install dependencies (cached)
    - Run pytest
    - Upload coverage

  backend-lint:
    - Setup Python + uv
    - Run ruff check
    - Run ruff format --check
    - Run mypy

  frontend-lint:
    - Setup Node.js
    - Install dependencies (cached)
    - Run eslint
    - Run tsc --noEmit

  # All jobs run in parallel for speed
```

---

## Secrets Required

### GitHub Secrets (Repository Level)

| Secret | Purpose | Environment |
|--------|---------|-------------|
| `RAILWAY_TOKEN` | Railway API access | All |
| `VERCEL_TOKEN` | Vercel API access | All |
| `VERCEL_ORG_ID` | Vercel organization | All |
| `VERCEL_PROJECT_ID` | Vercel project | All |

### Railway Environment Variables (Per Environment)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection |
| `REDIS_URL` | Redis connection |
| `JWT_SECRET_KEY` | JWT signing |
| `CLERK_SECRET_KEY` | Clerk authentication |
| `ANTHROPIC_API_KEY` | Claude API |
| `RESEND_API_KEY` | Email service |
| `STRIPE_SECRET_KEY` | Payment processing |
| `XERO_CLIENT_ID` | Xero OAuth |
| `XERO_CLIENT_SECRET` | Xero OAuth |

### Vercel Environment Variables (Per Environment)

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | Backend API URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk public key |
| `CLERK_SECRET_KEY` | Clerk secret key |

---

## Health Check Strategy

### Backend Health Endpoint

```
GET /health
Response: { "status": "healthy", "version": "1.2.3", "database": "connected", "redis": "connected" }
```

### Railway Health Check Configuration

- Path: `/health`
- Interval: 30 seconds
- Timeout: 10 seconds
- Healthy threshold: 1
- Unhealthy threshold: 3

### Deployment Health Verification

1. Deploy new version alongside existing
2. Wait for health checks to pass
3. Route traffic to new version
4. Keep old version for 10 minutes (quick rollback)
5. Remove old version after successful verification

---

## Rollback Strategy

### Automatic Rollback

- If health checks fail after deployment
- Railway automatically reverts to previous healthy deployment

### Manual Rollback

```bash
# Via Railway CLI
railway rollback

# Via GitHub
# Revert merge commit and push to trigger new deployment
git revert HEAD
git push origin main
```

---

## Next Steps

1. **Phase 0**: Execute research tasks and generate research.md
2. **Phase 1**: Generate quickstart.md with deployment guide
3. **Phase 2**: Generate tasks.md with implementation checklist
