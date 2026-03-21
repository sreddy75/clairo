# Research: CI/CD Pipeline & Production Deployment

**Feature**: 042-cicd-production-deployment
**Date**: 2026-01-04
**Status**: Complete

---

## 1. GitHub Actions with uv (Python Package Manager)

### Decision: Use `astral-sh/setup-uv` action with caching

### Rationale
- Official action maintained by Astral (creators of uv)
- Built-in cache support optimized for CI
- Supports all uv-supported platforms
- Automatically runs `uv cache prune --ci` to reduce cache size

### Implementation

```yaml
- name: Setup uv
  uses: astral-sh/setup-uv@v5
  with:
    enable-cache: true
    cache-dependency-glob: "uv.lock"

- name: Install dependencies
  run: uv sync --frozen
  working-directory: backend
```

### Caching Strategy
- Cache key includes: OS, workflow name, job name, `uv.lock` hash, calendar week
- Caches expire weekly or when `uv.lock` changes
- Three directories cached: `~/.cache/uv`, `~/.local/share/uv`, `.venv`

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| `astral-sh/setup-uv` | Official, well-maintained, built-in cache | None significant | **Selected** |
| `hynek/setup-cached-uv` | Good defaults | Less official | Rejected |
| `actions/setup-python` + pip | GitHub caches Python versions | Slower than uv | Rejected |

### Sources
- [Using uv in GitHub Actions - Official Docs](https://docs.astral.sh/uv/guides/integration/github/)
- [astral-sh/setup-uv GitHub](https://github.com/astral-sh/setup-uv)
- [A Github Actions setup for Python projects in 2025](https://ber2.github.io/posts/2025_github_actions_python/)

---

## 2. Railway Deployment for FastAPI + Celery

### Decision: Use Dockerfiles with railway.toml configuration

### Rationale
- Railway automatically detects Dockerfiles and uses them for builds
- Custom Dockerfiles are faster (15 seconds total) vs Nixpacks
- Multi-service deployment supports separate services for API, Worker, Beat
- Health checks ensure zero-downtime deployments

### Multi-Service Architecture

```
Railway Project
├── backend-api        # FastAPI service
├── backend-worker     # Celery worker
├── backend-beat       # Celery beat scheduler
├── postgres           # Managed PostgreSQL
└── redis              # Managed Redis
```

### Railway Configuration (railway.toml)

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile.prod"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 10
restartPolicyType = "always"
```

### Celery Worker Pattern
- Celery workers run continuously, monitoring Redis queue
- Workers fetch data, save to database, handle conflicts gracefully
- For very long jobs (up to 12 hours), use cron jobs instead

### Production Best Practices
- Use Gunicorn with Uvicorn workers for multi-core utilization
- Set worker count equal to available CPU cores
- Async Uvicorn workers handle concurrent requests efficiently

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Dockerfile | Fast builds, full control | More setup | **Selected** |
| Nixpacks | Zero config | Slower, less control | Rejected |
| Railway Templates | Quick start | Limited customization | Rejected for prod |

### Sources
- [Deploy a FastAPI App - Railway Docs](https://docs.railway.com/guides/fastapi)
- [Deploy FastAPI to Railway with Dockerfile](https://www.codingforentrepreneurs.com/blog/deploy-fastapi-to-railway-with-this-dockerfile)
- [FastAPI production deployment best practices](https://render.com/articles/fastapi-production-deployment-best-practices)

---

## 3. Vercel Deployment for Next.js

### Decision: Use Vercel's built-in GitHub integration + GitHub Actions for control

### Rationale
- Vercel for GitHub automatically deploys every push
- Preview URLs generated for every PR
- Production deployments on merge to main
- Can add GitHub Actions layer for additional control (tests before deploy)

### Preview Deployment Strategy

**Option A: Vercel Native (Recommended for simplicity)**
- Automatic preview for every push to any branch
- Unique URL: `{project}-{branch}-{team}.vercel.app`
- Comment added to PR with preview URL
- No GitHub Actions required

**Option B: GitHub Actions + Vercel CLI (More control)**
```yaml
- name: Deploy Preview
  run: |
    vercel pull --yes --environment=preview --token=${{ secrets.VERCEL_TOKEN }}
    vercel build --token=${{ secrets.VERCEL_TOKEN }}
    vercel deploy --prebuilt --token=${{ secrets.VERCEL_TOKEN }}
```

### Required Secrets
| Secret | Purpose |
|--------|---------|
| `VERCEL_TOKEN` | API authentication |
| `VERCEL_ORG_ID` | Organization/team ID |
| `VERCEL_PROJECT_ID` | Project ID |

### Production Deployment
- Triggered on merge to main
- Uses `vercel deploy --prod --prebuilt`
- Automatic rollback via git revert + new deploy

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Vercel native git | Zero config, automatic previews | Less CI control | **Selected for previews** |
| GitHub Actions + Vercel CLI | Full control, custom steps | More setup | Selected for production |
| Self-hosted Next.js | Full control | No CDN, more ops work | Rejected |

### Sources
- [Deploying GitHub Projects with Vercel](https://vercel.com/docs/git/vercel-for-github)
- [How can I use GitHub Actions with Vercel?](https://vercel.com/kb/guide/how-can-i-use-github-actions-with-vercel)
- [Deploy Next.js to Vercel with GitHub Actions](https://www.ali-dev.com/blog/deploying-next-js-to-vercel-with-github-actions-a-quick-guide)

---

## 4. Database Migrations in CI/CD

### Decision: Run Alembic migrations as deployment step before app starts

### Rationale
- Migrations must complete before new app version starts
- Prevents schema mismatches between code and database
- Failure stops deployment, leaving old version running

### Implementation Strategy

```dockerfile
# In Dockerfile.prod
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port $PORT"]
```

### Migration Best Practices
1. **Backward-compatible migrations**: New code should work with old schema during transition
2. **Separate migration job** (optional): Run migrations in dedicated job before deploy
3. **Migration locking**: Use advisory locks to prevent concurrent migrations
4. **Rollback strategy**: Maintain downgrade scripts for all migrations

### Railway-Specific Considerations
- Railway runs one instance at a time during deployment
- Health check waits for migration + startup to complete
- If migration fails, deployment fails, old version stays active

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Startup migration | Simple, atomic | Blocks startup | **Selected** |
| Separate migration job | Parallel, visible | Complex, timing issues | Rejected |
| Manual migrations | Control | Error-prone, slow | Rejected |

---

## 5. Secrets Management

### Decision: Platform-native secrets (GitHub Secrets + Railway/Vercel env vars)

### Rationale
- GitHub Secrets: Encrypted, not exposed in logs, easy rotation
- Railway/Vercel env vars: Per-environment, encrypted at rest
- No additional secrets management service needed for beta

### Secrets Organization

**GitHub Repository Secrets** (CI/CD access):
```
RAILWAY_TOKEN          # Railway API token
VERCEL_TOKEN           # Vercel API token
VERCEL_ORG_ID          # Vercel organization
VERCEL_PROJECT_ID      # Vercel project
```

**Railway Environment Variables** (per-environment):
```
# Staging
DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, ...

# Production
DATABASE_URL, REDIS_URL, JWT_SECRET_KEY, ...
```

**Vercel Environment Variables** (per-environment):
```
NEXT_PUBLIC_API_URL
NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY
CLERK_SECRET_KEY
```

### Security Practices
1. Never log secrets (GitHub Actions masks them automatically)
2. Use environment-specific secrets (staging vs production)
3. Rotate secrets periodically (manual process for beta)
4. Audit secret access via platform logs

### Alternatives Considered
| Option | Pros | Cons | Decision |
|--------|------|------|----------|
| Platform-native | Simple, no extra service | Manual rotation | **Selected** |
| AWS Secrets Manager | Rotation, audit | Extra cost, complexity | Future consideration |
| HashiCorp Vault | Enterprise-grade | Overkill for beta | Rejected |

---

## 6. Health Checks and Rollback

### Decision: Railway native health checks with automatic rollback

### Rationale
- Railway provides built-in health check support
- Failed health checks automatically revert to previous deployment
- Simple configuration via railway.toml

### Health Check Configuration

```toml
[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 10
numReplicas = 1
```

### Health Endpoint Implementation

```python
@router.get("/health")
async def health_check(db: AsyncSession = Depends(get_db)):
    # Check database
    try:
        await db.execute(text("SELECT 1"))
        db_status = "connected"
    except Exception:
        db_status = "disconnected"

    # Check Redis
    try:
        await redis.ping()
        redis_status = "connected"
    except Exception:
        redis_status = "disconnected"

    healthy = db_status == "connected" and redis_status == "connected"

    return {
        "status": "healthy" if healthy else "unhealthy",
        "database": db_status,
        "redis": redis_status,
        "version": settings.VERSION
    }
```

### Rollback Strategies

| Strategy | When to Use | How |
|----------|-------------|-----|
| Automatic | Health check fails | Railway reverts automatically |
| Manual (Railway) | Performance issue | `railway rollback` CLI |
| Manual (Git) | Any issue | Revert commit, push to main |

---

## 7. CI Pipeline Performance Optimization

### Decision: Parallel jobs with aggressive caching

### Rationale
- Backend and frontend checks are independent
- Parallel execution reduces total CI time
- Caching prevents redundant dependency installation

### Optimized Job Structure

```yaml
jobs:
  backend-test:      # ~3-4 min
    runs-on: ubuntu-latest
    steps:
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pytest

  backend-lint:      # ~1-2 min (parallel with test)
    runs-on: ubuntu-latest
    steps:
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run mypy .

  frontend-lint:     # ~2-3 min (parallel)
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-node@v4
      - run: npm ci
      - run: npm run lint
      - run: npm run typecheck
```

### Expected CI Times
| Job | Time (cached) | Time (cold) |
|-----|---------------|-------------|
| Backend test | 2-3 min | 4-5 min |
| Backend lint | 1-2 min | 2-3 min |
| Frontend lint | 1-2 min | 3-4 min |
| **Total (parallel)** | **3-4 min** | **5-6 min** |

---

## Summary of Decisions

| Area | Decision | Confidence |
|------|----------|------------|
| Python CI setup | `astral-sh/setup-uv` with caching | High |
| Railway deployment | Dockerfile + railway.toml | High |
| Vercel deployment | Native git integration + CLI for prod | High |
| Database migrations | Startup migration in Dockerfile | High |
| Secrets management | Platform-native (GitHub/Railway/Vercel) | High |
| Health checks | Railway native with `/health` endpoint | High |
| CI optimization | Parallel jobs, aggressive caching | High |

---

## Unresolved Items

None - all research areas have clear decisions.

---

## References

1. [uv GitHub Actions Guide](https://docs.astral.sh/uv/guides/integration/github/)
2. [Railway FastAPI Deployment](https://docs.railway.com/guides/fastapi)
3. [Vercel GitHub Integration](https://vercel.com/docs/git/vercel-for-github)
4. [FastAPI Production Best Practices](https://render.com/articles/fastapi-production-deployment-best-practices)
