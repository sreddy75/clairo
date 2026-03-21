# Quickstart: CI/CD Pipeline & Production Deployment

**Feature**: 042-cicd-production-deployment
**Date**: 2026-01-04

---

## Overview

This guide explains how to use the CI/CD pipeline for Clairo. The system automatically tests, builds, and deploys your code changes.

---

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout main
git pull origin main
git checkout -b feature/your-feature-name
```

### 2. Make Your Changes

Write code, add tests, commit regularly:

```bash
git add .
git commit -m "feat: add new feature"
```

### 3. Push and Create PR

```bash
git push origin feature/your-feature-name
```

Then create a Pull Request on GitHub targeting `main`.

### 4. Automated Checks Run

When you create a PR, the CI pipeline automatically:

| Check | What It Does | Pass Criteria |
|-------|--------------|---------------|
| Backend Tests | Runs pytest | All tests pass |
| Backend Lint | Runs ruff check | No lint errors |
| Backend Types | Runs mypy | No type errors |
| Frontend Lint | Runs eslint | No lint errors |
| Frontend Types | Runs tsc | No type errors |

### 5. Preview Deployment

- Vercel automatically creates a preview URL
- Preview URL is posted as a comment on your PR
- Share this URL with reviewers to test changes

### 6. Get Approval and Merge

- Request review from team members
- Address any feedback
- Merge when approved and all checks pass

### 7. Automatic Production Deployment

- Merge to `main` triggers production deployment
- Backend deploys to Railway
- Frontend deploys to Vercel
- Database migrations run automatically
- Team is notified when deployment completes

---

## Environment URLs

| Environment | Backend URL | Frontend URL | When Updated |
|-------------|-------------|--------------|--------------|
| Production | `https://api.clairo.ai` | `https://app.clairo.ai` | Merge to `main` |
| Staging | `https://api-staging.clairo.ai` | `https://staging.clairo.ai` | Merge to `develop` |
| Preview | N/A | `https://clairo-{branch}.vercel.app` | Every PR push |

---

## Common Tasks

### Running Tests Locally (Before Pushing)

```bash
# Backend
cd backend
uv run pytest                    # Run all tests
uv run pytest -x                 # Stop on first failure
uv run ruff check .              # Check linting
uv run ruff format .             # Auto-format code
uv run mypy app/                 # Check types

# Frontend
cd frontend
npm run lint                     # Check linting
npm run lint:fix                 # Auto-fix lint issues
npm run typecheck                # Check TypeScript types
```

### Checking CI Status

1. Go to your PR on GitHub
2. Scroll to "Checks" section
3. Click on any check to see details/logs

### Fixing Failed Checks

| Check Failed | How to Fix |
|--------------|------------|
| Backend Tests | Run `uv run pytest` locally, fix failures |
| Backend Lint | Run `uv run ruff format .` to auto-fix |
| Backend Types | Fix type errors shown in mypy output |
| Frontend Lint | Run `npm run lint:fix` to auto-fix |
| Frontend Types | Fix TypeScript errors shown in output |

### Viewing Deployment Status

- **GitHub Actions**: Check the "Actions" tab in GitHub repo
- **Railway**: Go to Railway dashboard → Project → Deployments
- **Vercel**: Go to Vercel dashboard → Project → Deployments

---

## Rollback Procedures

### If Production Deployment Fails

1. Railway automatically keeps the previous version running
2. Check Railway dashboard for deployment logs
3. Fix the issue and push a new commit

### If Production Has Issues After Deploy

**Option 1: Quick Rollback (Railway)**
```bash
# Via Railway CLI
railway rollback
```

**Option 2: Git Revert**
```bash
git revert HEAD
git push origin main
# This triggers a new deployment with the previous code
```

### If Database Migration Fails

1. Deployment will fail automatically
2. Previous version stays running
3. Fix migration and push new commit
4. If needed, manually revert migration:
   ```bash
   railway run alembic downgrade -1
   ```

---

## Adding New Environment Variables

### For Backend (Railway)

1. Go to Railway dashboard
2. Select the service (backend-api, backend-worker, or backend-beat)
3. Click "Variables"
4. Add variable for each environment (staging, production)

### For Frontend (Vercel)

1. Go to Vercel dashboard
2. Select the project
3. Go to "Settings" → "Environment Variables"
4. Add variable, select which environments it applies to

### For CI Pipeline (GitHub)

1. Go to GitHub repo → Settings → Secrets and variables → Actions
2. Click "New repository secret"
3. Add secret name and value

---

## Troubleshooting

### CI Taking Too Long

- Check if caches are working (first run after cache expires takes longer)
- Ensure `uv.lock` and `package-lock.json` are committed
- Parallel jobs should complete in ~5 minutes

### Preview Deployment Not Working

- Check Vercel dashboard for deployment errors
- Ensure `VERCEL_TOKEN` secret is set in GitHub
- Check PR for Vercel bot comment with preview URL

### Production Deployment Stuck

- Check Railway dashboard for deployment logs
- Verify health check endpoint is responding
- Check database migration logs

### Cannot Access Production Environment

- Verify you're using correct URLs
- Check if deployment completed successfully
- Verify environment variables are set correctly

---

## Security Notes

1. **Never commit secrets** - Use environment variables
2. **Never log sensitive data** - CI masks secrets automatically
3. **Review before merge** - Code review catches security issues
4. **Use staging first** - Test changes in staging before production

---

## Quick Reference

```bash
# Create feature branch
git checkout -b feature/my-feature

# Run all checks locally
cd backend && uv run pytest && uv run ruff check . && uv run mypy app/
cd frontend && npm run lint && npm run typecheck

# Push and create PR
git push origin feature/my-feature

# After merge, watch deployment
# - Railway: https://railway.app/dashboard
# - Vercel: https://vercel.com/dashboard
```

---

## Support

- **CI/CD Issues**: Check GitHub Actions logs
- **Deployment Issues**: Check Railway/Vercel dashboards
- **General Questions**: Ask in team Slack channel
