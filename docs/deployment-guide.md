# Clairo Deployment Guide

This guide covers production deployment for the Clairo platform.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                      RAILWAY                             │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐     │
│  │ backend-api │  │backend-worker│ │ backend-beat │     │
│  │  (FastAPI)  │  │  (Celery)   │  │  (Celery)   │     │
│  └─────────────┘  └─────────────┘  └─────────────┘     │
│         │                │                │             │
│         └────────────────┼────────────────┘             │
│                          │                              │
│  ┌─────────────┐  ┌─────────────┐                      │
│  │  PostgreSQL │  │    Redis    │                      │
│  │  (Managed)  │  │  (Managed)  │                      │
│  └─────────────┘  └─────────────┘                      │
└─────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────┐
│                       VERCEL                             │
├─────────────────────────────────────────────────────────┤
│  ┌─────────────────────────────────────────────┐       │
│  │              Next.js Frontend               │       │
│  │            (Sydney Region - syd1)           │       │
│  └─────────────────────────────────────────────┘       │
└─────────────────────────────────────────────────────────┘
```

## Database Migrations

### How Migrations Work

Migrations run automatically during deployment as part of the container startup:

```dockerfile
CMD sh -c "python -m alembic upgrade head && gunicorn app.main:app ..."
```

**Flow**:
1. New container starts
2. Alembic runs `upgrade head` to apply pending migrations
3. If migrations succeed, Gunicorn starts the API
4. If migrations fail, container exits and deployment fails
5. Railway keeps the previous version running

### Migration Best Practices

1. **Backward-compatible changes**: New code should work with old schema during transition
2. **Test migrations locally**: Run `alembic upgrade head` before pushing
3. **One migration per PR**: Easier to track and rollback
4. **Avoid destructive changes**: Use multi-step migrations for column renames/deletes

### Handling Migration Failures

**If migration fails during deployment**:

1. Check Railway deployment logs for error details
2. Previous version remains running (no downtime)
3. Fix the migration and push a new commit
4. If stuck, manually connect to database:
   ```bash
   railway run python -m alembic current
   railway run python -m alembic downgrade -1
   ```

**Common issues**:

| Issue | Solution |
|-------|----------|
| Column already exists | Check if migration ran partially, fix manually |
| Foreign key violation | Ensure referenced data exists |
| Timeout | Break large migrations into smaller batches |

## Health Checks

### Endpoints

| Endpoint | Purpose | Used By |
|----------|---------|---------|
| `/health` | Basic liveness check | Load balancer |
| `/health/ready` | Full readiness check | Railway health checks |

### What `/health/ready` Checks

1. **Database**: Executes `SELECT 1` to verify connection
2. **Redis**: Pings Redis to verify cache is accessible

### Health Check Configuration

Railway is configured to check `/health/ready`:
- **Interval**: 30 seconds
- **Timeout**: 30 seconds
- **Start period**: 30 seconds (allows for migrations)
- **Retries**: 3

## Deployment Process

### Automatic (via CI/CD)

1. Push to `main` branch
2. GitHub Actions runs CI checks
3. If checks pass, deployment workflow starts
4. Backend deploys to Railway (with migrations)
5. Frontend deploys to Vercel
6. Health checks verify deployment
7. Commit status updated

### Manual Deployment

**Backend (Railway CLI)**:
```bash
cd /path/to/clairo
railway login
railway link
railway up --service backend-api
```

**Frontend (Vercel CLI)**:
```bash
cd frontend
vercel login
vercel --prod
```

## Environment Variables

See `/.env.production.template` for required variables.

### Adding New Variables

1. Add to `.env.production.template` (no values)
2. Update documentation
3. Add actual value in Railway/Vercel dashboard
4. Deploy changes

## Monitoring

### Logs

- **Railway**: Dashboard > Project > Service > Logs
- **Vercel**: Dashboard > Project > Deployments > Functions tab

### Errors

- **Sentry**: Errors tracked automatically when SENTRY_DSN is set
- **GitHub Actions**: Check Actions tab for deployment failures

## Rollback

### Railway (Backend)

```bash
# Via CLI
railway rollback

# Via Dashboard
# 1. Go to Service > Deployments
# 2. Find the working deployment
# 3. Click "Redeploy"
```

### Vercel (Frontend)

```bash
# Redeploy previous version
vercel rollback
```

### Git Revert (Both)

```bash
git revert HEAD
git push origin main
# This triggers a new deployment with the previous code
```

## Troubleshooting

### Deployment Stuck

1. Check Railway/Vercel dashboard for deployment status
2. Check GitHub Actions for CI failures
3. Verify secrets are set correctly
4. Check health endpoint manually

### Container Won't Start

1. Check container logs in Railway
2. Verify DATABASE_URL and REDIS_URL are correct
3. Check if migrations are failing
4. Try running locally with production environment

### Health Check Failing

1. Verify database is accessible from Railway network
2. Check Redis connection string
3. Ensure migrations completed successfully
4. Check for port binding issues (use $PORT from Railway)
