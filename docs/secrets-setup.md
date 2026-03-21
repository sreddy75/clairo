# Clairo Secrets Management Guide

This guide covers how to set up and manage secrets for Clairo deployments.

## Overview

Clairo uses platform-native secrets management:
- **GitHub Secrets**: CI/CD pipeline secrets
- **Railway Variables**: Backend runtime secrets
- **Vercel Environment Variables**: Frontend runtime secrets

## GitHub Repository Secrets

These secrets are used by GitHub Actions workflows.

### Required Secrets

| Secret | Purpose | How to Get |
|--------|---------|------------|
| `RAILWAY_TOKEN` | Railway API access | [Railway Dashboard](https://railway.app/account/tokens) → Generate Token |
| `RAILWAY_PROJECT_ID` | Production project ID | Railway Dashboard → Project Settings |
| `RAILWAY_STAGING_PROJECT_ID` | Staging project ID | Railway Dashboard → Project Settings |
| `VERCEL_TOKEN` | Vercel API access | [Vercel Dashboard](https://vercel.com/account/tokens) → Create Token |
| `VERCEL_ORG_ID` | Vercel organization | Vercel Dashboard → Settings → General |
| `VERCEL_PROJECT_ID` | Production project ID | Vercel Dashboard → Project → Settings → General |
| `VERCEL_STAGING_PROJECT_ID` | Staging project ID | Vercel Dashboard → Project → Settings → General |
| `PRODUCTION_BACKEND_URL` | Production API URL | `https://api.clairo.ai` |
| `STAGING_API_URL` | Staging API URL | `https://api-staging.clairo.ai` |

### How to Add GitHub Secrets

1. Go to your repository on GitHub
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Enter the secret name and value
5. Click **Add secret**

### Using GitHub CLI

```bash
# Add a secret
gh secret set RAILWAY_TOKEN --body "your-token-here"

# Add from file
gh secret set RAILWAY_TOKEN < railway-token.txt

# List secrets (names only, values hidden)
gh secret list
```

## Railway Environment Variables

These variables are set per-service in the Railway dashboard.

### Backend API Service

```bash
# Required
DATABASE_URL=postgresql+asyncpg://...
REDIS_URL=redis://...
JWT_SECRET_KEY=...
CLERK_SECRET_KEY=...
ANTHROPIC_API_KEY=...

# Optional
SENTRY_DSN=...
```

### Setting Railway Variables

**Option 1: Railway Dashboard**
1. Go to [Railway Dashboard](https://railway.app/dashboard)
2. Select your project
3. Click on the service (e.g., backend-api)
4. Go to **Variables** tab
5. Add variables using RAW Editor or individual inputs

**Option 2: Railway CLI**
```bash
# Link to project
railway link

# Set variable
railway variables set JWT_SECRET_KEY="your-secret"

# Set multiple variables from .env file
railway variables set < .env.production

# View variables (redacted)
railway variables
```

### Variable Sharing

For variables needed by multiple services:
1. Create a **Shared Variable Group** in Railway
2. Link services to the group
3. Variables are automatically available to all linked services

## Vercel Environment Variables

### Frontend Variables

| Variable | Purpose | Environment |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | Backend API URL | All |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | Clerk public key | All |
| `CLERK_SECRET_KEY` | Clerk secret key | All |
| `NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY` | Stripe public key | All |
| `NEXT_PUBLIC_ENVIRONMENT` | Environment name | All |

### Setting Vercel Variables

**Option 1: Vercel Dashboard**
1. Go to [Vercel Dashboard](https://vercel.com/dashboard)
2. Select your project
3. Go to **Settings** → **Environment Variables**
4. Add variable with name, value, and target environments

**Option 2: Vercel CLI**
```bash
# Add variable
vercel env add NEXT_PUBLIC_API_URL production

# Pull environment to .env.local
vercel env pull .env.local

# List variables
vercel env ls
```

## Secret Rotation

### When to Rotate Secrets

- On team member departure
- If secret may have been exposed
- Periodically (recommended: every 90 days)

### How to Rotate

1. Generate new secret value
2. Update in Railway/Vercel dashboard
3. Trigger new deployment (or wait for next deploy)
4. Verify application works with new secret
5. Invalidate old secret (if possible)

### Secrets That Require Rotation

| Secret | Rotation Method |
|--------|-----------------|
| JWT_SECRET_KEY | Generate new key, deploy, old tokens invalidate |
| STRIPE_SECRET_KEY | Generate in Stripe, update Railway |
| CLERK_SECRET_KEY | Regenerate in Clerk, update Railway + Vercel |
| ANTHROPIC_API_KEY | Generate new key in Anthropic console |
| RAILWAY_TOKEN | Generate new in Railway, update GitHub |
| VERCEL_TOKEN | Generate new in Vercel, update GitHub |

## Security Best Practices

### Do's

- ✅ Use different secrets for staging and production
- ✅ Use test/sandbox API keys in staging where possible
- ✅ Rotate secrets periodically
- ✅ Use strong, randomly generated secrets
- ✅ Limit secret access to those who need it
- ✅ Audit secret access via platform logs

### Don'ts

- ❌ Commit secrets to Git (ever!)
- ❌ Share secrets in Slack/email
- ❌ Use the same secret across environments
- ❌ Use weak or predictable secrets
- ❌ Keep secrets in code comments
- ❌ Log secret values (even partial)

## Generating Secure Secrets

```bash
# Generate 256-bit key (for JWT_SECRET_KEY)
openssl rand -hex 32

# Generate 128-bit key
openssl rand -hex 16

# Generate URL-safe token
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Troubleshooting

### "Secret not found" errors

1. Check variable name spelling (case-sensitive)
2. Verify variable is set for correct environment
3. Redeploy after adding variables
4. Check if variable needs `NEXT_PUBLIC_` prefix (frontend)

### Variable not updating

1. Redeploy the service after changing variables
2. Clear browser cache for frontend changes
3. Check if old pods are still running (Railway)

### Debugging locally

```bash
# Pull production variables (be careful!)
vercel env pull .env.production.local

# Or create from template
cp .env.production.template .env.local
# Then fill in values manually
```
