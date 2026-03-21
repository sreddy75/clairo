# Clairo Rollback Guide

This guide covers how to roll back deployments when issues occur in production or staging.

## Quick Reference

| Situation | Action |
|-----------|--------|
| Backend broken after deploy | `railway rollback` or Railway dashboard |
| Frontend broken after deploy | `vercel rollback` or Vercel dashboard |
| Database migration issue | See "Migration Rollback" section |
| Need to revert code | `git revert HEAD && git push` |

## Automatic Rollback

### Railway Health Checks

Railway automatically rolls back if:
- Health check fails after deployment
- Container crashes during startup
- Migration fails

**Configuration** (in `railway.toml`):
```toml
[deploy]
healthcheckPath = "/health/ready"
healthcheckTimeout = 30
restartPolicyType = "ON_FAILURE"
restartPolicyMaxRetries = 10
```

### What Happens During Auto-Rollback

1. New deployment starts
2. Migration runs (if any)
3. Health check is called
4. If health check fails 3 times:
   - New deployment is stopped
   - Previous healthy deployment is kept active
   - Deployment marked as failed
   - GitHub commit status updated

## Manual Rollback

### Railway (Backend)

**Option 1: Railway CLI**
```bash
# Authenticate
railway login

# Link to project
railway link

# Rollback to previous deployment
railway rollback
```

**Option 2: Railway Dashboard**
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your project → Select service (backend-api)
3. Go to "Deployments" tab
4. Find the last working deployment
5. Click the three dots menu → "Redeploy"

**Option 3: Specific Deployment**
```bash
# List recent deployments
railway status

# Redeploy specific version (if available in your Railway plan)
# Usually requires dashboard for this
```

### Vercel (Frontend)

**Option 1: Vercel CLI**
```bash
# Authenticate
vercel login

# Rollback to previous production deployment
vercel rollback

# Or rollback to specific deployment
vercel rollback [deployment-url-or-id]
```

**Option 2: Vercel Dashboard**
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to "Deployments" tab
4. Find the last working deployment
5. Click the three dots menu → "Promote to Production"

### Git Revert (Both Services)

If you need to revert the code itself:

```bash
# Revert the last commit
git revert HEAD

# Push to trigger new deployment
git push origin main
```

This creates a new commit that undoes the changes, triggering a fresh deployment.

## Migration Rollback

### When to Roll Back Migrations

- Migration caused data corruption
- Schema change breaks running queries
- Migration is incompatible with running code

### How to Roll Back Migrations

**Option 1: Via Railway (Recommended)**
```bash
# Connect to Railway environment
railway run python -m alembic current

# Downgrade one migration
railway run python -m alembic downgrade -1

# Or downgrade to specific revision
railway run python -m alembic downgrade abc123
```

**Option 2: Via Direct Database Connection**
```bash
# Get DATABASE_URL from Railway
railway variables

# Run alembic locally pointing to production DB (be very careful!)
DATABASE_URL="..." alembic downgrade -1
```

### Important Considerations

1. **Data Loss**: Downgrade migrations may drop columns/tables
2. **Running Code**: Ensure running code is compatible with old schema
3. **Order**: Roll back code first, then migrations
4. **Testing**: Always test downgrade migrations in staging first

## Rollback Decision Tree

```
Issue detected in production?
│
├── Frontend only? (UI broken, no API calls affected)
│   └── Roll back Vercel → vercel rollback
│
├── Backend API broken?
│   ├── Health checks failing?
│   │   └── Should auto-rollback. If not: railway rollback
│   └── API returning errors?
│       ├── Database issue?
│       │   └── Check migrations, consider alembic downgrade
│       └── Code issue?
│           └── railway rollback OR git revert
│
├── Both frontend and backend broken?
│   └── Roll back backend first, then frontend
│
└── Data corruption?
    └── DO NOT auto-rollback. Assess damage first.
        Contact team lead. May need database restore.
```

## Post-Rollback Checklist

After any rollback:

- [ ] Verify services are healthy (`/health/ready` returns OK)
- [ ] Check Sentry for new errors
- [ ] Verify key user flows work
- [ ] Document what happened
- [ ] Create post-mortem if significant impact
- [ ] Plan fix for the reverted changes

## Emergency Contacts

| Role | Contact | When to Contact |
|------|---------|-----------------|
| On-call Engineer | (See PagerDuty) | Any production issue |
| Team Lead | (Internal) | Major incidents |
| Database Admin | (Internal) | Data corruption |

## Preventing Rollbacks

1. **Test locally** before pushing
2. **Test in staging** before merging to main
3. **Use feature flags** for risky changes
4. **Deploy during low-traffic periods** for major changes
5. **Monitor after deploy** - watch Sentry and metrics
