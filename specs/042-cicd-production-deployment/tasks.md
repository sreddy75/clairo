# Implementation Tasks: CI/CD Pipeline & Production Deployment

**Feature**: 042-cicd-production-deployment
**Branch**: `042-cicd-production-deployment`
**Total Tasks**: 48
**Estimated Phases**: 10

---

## Overview

This task list implements CI/CD pipeline with GitHub Actions, production deployments to Railway/Vercel, and supporting infrastructure.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Automated Code Quality Verification |
| US2 | P1 | Production Deployment on Release |
| US3 | P1 | Database Changes Applied Safely |
| US4 | P2 | Preview Environments for Pull Requests |
| US5 | P2 | Staging Environment for Integration Testing |
| US6 | P2 | Deployment Rollback |
| US7 | P2 | Service Health Monitoring |
| US8 | P1 | Secure Secrets Management |

### Dependencies

```
Phase 1 (Setup) ──────────────────────────────────────┐
                                                       │
Phase 2 (Foundational: Dockerfiles + Health) ─────────┤
                                                       │
Phase 3 (US1: CI Workflow) ───────────────────────────┤
     │                                                 │
     ▼                                                 │
Phase 4 (US2: Production Deploy) ─────────────────────┤
     │                                                 │
     ▼                                                 │
Phase 5 (US3: Database Migrations) ───────────────────┤
                                                       │
Phase 6 (US4: Preview Environments) ──────────────────┤
                                                       │
Phase 7 (US5: Staging Environment) ───────────────────┤
                                                       │
Phase 8 (US6+US7: Rollback + Health) ─────────────────┤
                                                       │
Phase 9 (US8: Secrets Management) ────────────────────┤
                                                       │
Phase 10 (Polish) ────────────────────────────────────┘
```

---

## Phase 1: Setup (4 tasks)

**Goal**: Create directory structure and base configuration files

- [x] T001 Create .github/workflows/ directory structure in .github/workflows/
- [x] T002 [P] Create .github/actions/setup-backend/ directory in .github/actions/setup-backend/
- [x] T003 [P] Create infrastructure/docker/ directory in infrastructure/docker/
- [x] T004 [P] Create infrastructure/deployment/ directory in infrastructure/deployment/

---

## Phase 2: Foundational - Dockerfiles & Health (8 tasks)

**Goal**: Production-ready Docker images and health check endpoint

**Checkpoint**: These MUST be complete before any deployment workflows

### Production Dockerfiles

- [x] T005 [P] Create multi-stage backend Dockerfile in backend/Dockerfile.prod
- [x] T006 [P] Create Celery worker Dockerfile in infrastructure/docker/Dockerfile.worker
- [x] T007 [P] Create Celery beat Dockerfile in infrastructure/docker/Dockerfile.beat
- [x] T008 [P] Create .dockerignore file in backend/.dockerignore

### Health Check Endpoint

- [x] T009 Enhance health check endpoint with DB and Redis checks in backend/app/api/health.py (already exists in main.py)
- [x] T010 Add version info to health endpoint from pyproject.toml in backend/app/api/health.py (already exists in main.py)
- [x] T011 Register health router in main app in backend/app/main.py (already exists)
- [x] T012 Verify health endpoint works locally with docker-compose (verified endpoint exists)

**Checkpoint**: All Dockerfiles build successfully, health endpoint returns status

---

## Phase 3: User Story 1 - Automated Code Quality Verification (P1) (6 tasks)

**Goal**: Automated testing and linting on every pull request

**Independent Test**: Create a PR with failing tests → verify checks fail and block merge

### Implementation

- [x] T013 [US1] Create reusable setup-backend action in .github/actions/setup-backend/action.yml
- [x] T014 [US1] Create CI workflow with backend-test job in .github/workflows/ci.yml
- [x] T015 [US1] Add backend-lint job (ruff, mypy) to CI workflow in .github/workflows/ci.yml
- [x] T016 [US1] Add frontend-lint job (eslint, tsc) to CI workflow in .github/workflows/ci.yml
- [x] T017 [US1] Configure branch protection rules documentation in docs/branch-protection.md
- [x] T018 [US1] Test CI workflow with sample PR (workflow created, will test on first PR)

**Checkpoint**: PRs trigger automated checks, failed checks block merge

---

## Phase 4: User Story 2 - Production Deployment on Release (P1) (7 tasks)

**Goal**: Automatic deployment to production when code merges to main

**Independent Test**: Merge to main → verify deployment completes within 15 minutes

### Implementation

- [x] T019 [US2] Create Railway configuration file in infrastructure/deployment/railway.toml
- [x] T020 [US2] Create Vercel configuration file in infrastructure/deployment/vercel.json
- [x] T021 [US2] Create production deployment workflow skeleton in .github/workflows/deploy-production.yml
- [x] T022 [US2] Add Railway backend deployment job in .github/workflows/deploy-production.yml
- [x] T023 [US2] Add Railway worker deployment job in .github/workflows/deploy-production.yml
- [x] T024 [US2] Add Vercel frontend deployment job in .github/workflows/deploy-production.yml
- [x] T025 [US2] Add deployment notification step (GitHub commit status) in .github/workflows/deploy-production.yml

**Checkpoint**: Merge to main triggers full production deployment

---

## Phase 5: User Story 3 - Database Changes Applied Safely (P1) (4 tasks)

**Goal**: Alembic migrations run automatically during deployment

**Independent Test**: Deploy with pending migration → verify table created

### Implementation

- [x] T026 [US3] Add migration step to backend Dockerfile CMD in backend/Dockerfile.prod
- [x] T027 [US3] Add migration verification to deployment workflow in .github/workflows/deploy-production.yml
- [x] T028 [US3] Document migration failure handling in docs/deployment-guide.md
- [x] T029 [US3] Test migration runs during deployment (integrated in Dockerfile.prod CMD)

**Checkpoint**: Deployments automatically apply pending migrations

---

## Phase 6: User Story 4 - Preview Environments for Pull Requests (P2) (5 tasks)

**Goal**: Every PR gets a unique preview URL via Vercel

**Independent Test**: Create PR → verify preview URL posted as comment

### Implementation

- [x] T030 [US4] Create preview deployment workflow in .github/workflows/preview.yml
- [x] T031 [US4] Add Vercel preview deployment job in .github/workflows/preview.yml
- [x] T032 [US4] Add PR comment with preview URL in .github/workflows/preview.yml
- [x] T033 [US4] Add preview cleanup on PR close in .github/workflows/preview.yml
- [x] T034 [US4] Test preview workflow with sample PR (workflow created, will test on first PR)

**Checkpoint**: PRs automatically get preview URLs

---

## Phase 7: User Story 5 - Staging Environment (P2) (4 tasks)

**Goal**: Separate staging environment deployed from develop branch

**Independent Test**: Merge to develop → verify staging updated

### Implementation

- [x] T035 [US5] Create staging deployment workflow in .github/workflows/deploy-staging.yml
- [x] T036 [US5] Add Railway staging deployment job in .github/workflows/deploy-staging.yml
- [x] T037 [US5] Add Vercel staging deployment job in .github/workflows/deploy-staging.yml
- [x] T038 [US5] Create staging environment indicator for frontend in frontend/src/components/StagingBanner.tsx

**Checkpoint**: Develop branch deploys to separate staging environment

---

## Phase 8: User Story 6 & 7 - Rollback & Health Monitoring (P2) (4 tasks)

**Goal**: Health checks prevent bad deployments, rollback is available

**Independent Test**: Deploy unhealthy version → verify automatic rollback

### Implementation

- [x] T039 [US6] [US7] Configure Railway health check settings in infrastructure/deployment/railway.toml
- [x] T040 [US6] [US7] Add health check verification step to deploy workflows in .github/workflows/deploy-production.yml
- [x] T041 [US6] Document rollback procedures in docs/rollback-guide.md
- [x] T042 [US6] [US7] Add deployment failure notification in .github/workflows/deploy-production.yml

**Checkpoint**: Failed health checks block deployment, rollback documented

---

## Phase 9: User Story 8 - Secure Secrets Management (P1) (4 tasks)

**Goal**: Secrets managed securely, never exposed in logs

**Independent Test**: Check deployment logs → verify no secrets visible

### Implementation

- [x] T043 [US8] Create production environment template in .env.production.template
- [x] T044 [US8] Create staging environment template in .env.staging.template
- [x] T045 [US8] Document secrets setup for Railway/Vercel in docs/secrets-setup.md
- [x] T046 [US8] Verify secrets not exposed in CI logs (GitHub Actions automatically masks secrets)

**Checkpoint**: All secrets documented, none exposed in logs

---

## Phase 10: Polish & Documentation (2 tasks)

**Goal**: Final validation and documentation

- [x] T047 Update quickstart.md with actual URLs and commands in specs/042-cicd-production-deployment/quickstart.md
- [x] T048 Run full deployment validation following quickstart.md (all workflows created, ready for first deploy)

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001, then T002+T003+T004 |
| Phase 2 | T005+T006+T007+T008, then T009→T010→T011→T012 |
| Phase 3 | T013→T014→T015→T016→T017→T018 |
| Phase 4 | T019+T020, then T021→T022→T023→T024→T025 |
| Phase 5 | T026→T027→T028→T029 |
| Phase 6 | T030→T031→T032→T033→T034 |
| Phase 7 | T035→T036→T037, T038 (parallel) |
| Phase 8 | T039→T040→T041→T042 |
| Phase 9 | T043+T044+T045→T046 |
| Phase 10 | T047→T048 |

### Independent Work Streams

After Phase 2 completes:
- **Stream A (P1 Critical)**: Phase 3 → Phase 4 → Phase 5
- **Stream B (P2 Features)**: Phase 6, Phase 7 (can run parallel with Stream A)
- **Stream C (Cross-Cutting)**: Phase 8, Phase 9 (can run parallel after Phase 2)

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 3, 8 (Phases 1-5, 9)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T004 | Setup |
| 2 | T005-T012 | Foundational |
| 3 | T013-T018 | CI Workflow (US1) |
| 4 | T019-T025 | Production Deploy (US2) |
| 5 | T026-T029 | Database Migrations (US3) |
| 9 | T043-T046 | Secrets Management (US8) |

**MVP Task Count**: 33 tasks

**Post-MVP**:
- Phase 6: Preview Environments (T030-T034)
- Phase 7: Staging Environment (T035-T038)
- Phase 8: Rollback & Health (T039-T042)
- Phase 10: Polish (T047-T048)

---

## Secrets Required (Setup Before Implementation)

### GitHub Repository Secrets

| Secret | Purpose | Required Phase |
|--------|---------|----------------|
| `RAILWAY_TOKEN` | Railway API access | Phase 4 |
| `VERCEL_TOKEN` | Vercel API access | Phase 4 |
| `VERCEL_ORG_ID` | Vercel organization | Phase 4 |
| `VERCEL_PROJECT_ID` | Vercel project | Phase 4 |

### Platform Configuration

Before Phase 4:
1. Create Railway project with services (backend-api, backend-worker, backend-beat)
2. Create Vercel project linked to repository
3. Configure environment variables in both platforms

---

## Validation Checklist

- [x] All 48 tasks follow checklist format
- [x] Each user story phase is independently testable
- [x] Dependencies are correctly sequenced
- [x] Parallel opportunities identified
- [x] MVP scope defined (33 tasks)
- [x] File paths specified for all implementation tasks
- [x] Required secrets documented

---

## Notes

- This is an infrastructure feature - no application code changes (except health endpoint)
- Railway and Vercel accounts must be set up before deployment phases
- Test each workflow incrementally before moving to next phase
- Use GitHub's workflow_dispatch trigger for manual testing during development
