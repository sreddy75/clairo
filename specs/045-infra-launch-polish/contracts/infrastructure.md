# Infrastructure Contracts: Infra & Launch Polish

**Date**: 2026-04-06

## No API Changes Required

This spec does not add or modify any API endpoints. All existing endpoints continue to work unchanged.

## Environment Variable Contract

### Production Environment Variables (all required)

| Variable | Service | Example | Notes |
|----------|---------|---------|-------|
| `DATABASE_URL` | PostgreSQL | `postgresql+asyncpg://clairo_app:...@host:5432/clairo` | Must use non-superuser role |
| `REDIS_URL` | Redis | `redis://default:...@host:6379` | Upstash or Railway Redis |
| `ENVIRONMENT` | App | `production` | Controls logging, Sentry, debug mode |
| `DEBUG` | App | `false` | Must be false in production |
| `CLERK_SECRET_KEY` | Clerk | `sk_live_...` | Production Clerk instance |
| `CLERK_PUBLISHABLE_KEY` | Clerk | `pk_live_...` | Production Clerk instance |
| `CLERK_JWKS_URL` | Clerk | `https://...clerk.com/.well-known/jwks.json` | Production JWKS endpoint |
| `STRIPE_SECRET_KEY` | Stripe | `sk_live_...` | Live mode Stripe key |
| `STRIPE_PUBLISHABLE_KEY` | Stripe | `pk_live_...` | Live mode Stripe key |
| `STRIPE_WEBHOOK_SECRET` | Stripe | `whsec_...` | Production webhook signing secret |
| `STRIPE_PRICE_STARTER` | Stripe | `price_...` | Live mode price ID |
| `RESEND_API_KEY` | Resend | `re_...` | clairo.com.au domain key |
| `RESEND_FROM_EMAIL` | Resend | `Clairo <noreply@clairo.com.au>` | Verified domain |
| `ANTHROPIC_API_KEY` | Anthropic | `sk-ant-...` | Claude API key |
| `VOYAGE_API_KEY` | Voyage | `pa-...` | Embeddings API key |
| `PINECONE_API_KEY` | Pinecone | `pcsk_...` | Vector DB key |
| `PINECONE_INDEX_HOST` | Pinecone | `https://...pinecone.io` | Index endpoint |
| `SENTRY_DSN` | Sentry | `https://...@sentry.io/...` | Error tracking |
| `SENTRY_ENVIRONMENT` | Sentry | `production` | Environment tag |
| `CORS_ORIGINS` | App | `https://www.clairo.com.au,https://clairo.com.au` | Production domains only |
| `MINIO_ENDPOINT` | R2/S3 | `...r2.cloudflarestorage.com` | S3-compatible endpoint |
| `MINIO_ACCESS_KEY` | R2/S3 | `...` | R2 access key |
| `MINIO_SECRET_KEY` | R2/S3 | `...` | R2 secret key |
| `MINIO_USE_SSL` | R2/S3 | `true` | Must be true in production |
| `TOKEN_ENCRYPTION_KEY` | App | `base64...` | OAuth token encryption |
| `XERO_CLIENT_ID` | Xero | `...` | Xero OAuth app |
| `XERO_CLIENT_SECRET` | Xero | `...` | Xero OAuth secret |
| `XERO_REDIRECT_URI` | Xero | `https://www.clairo.com.au/settings/integrations/xero/callback` | Production redirect |

### Frontend Environment Variables (Vercel)

| Variable | Example | Notes |
|----------|---------|-------|
| `NEXT_PUBLIC_API_URL` | `https://api.clairo.com.au` | Backend API URL |
| `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` | `pk_live_...` | Production Clerk |
| `NEXT_PUBLIC_CLERK_SIGN_IN_URL` | `/sign-in` | |
| `NEXT_PUBLIC_CLERK_SIGN_UP_URL` | `/sign-up` | |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_IN_URL` | `/dashboard` | |
| `NEXT_PUBLIC_CLERK_AFTER_SIGN_UP_URL` | `/onboarding` | |
| `NEXT_PUBLIC_POSTHOG_KEY` | `phc_...` | PostHog project key |
| `NEXT_PUBLIC_POSTHOG_HOST` | `https://us.i.posthog.com` | PostHog ingest |
| `NEXT_PUBLIC_SENTRY_DSN` | `https://...@sentry.io/...` | Frontend Sentry |

## DNS Records Required

| Record | Type | Value | Purpose |
|--------|------|-------|---------|
| `www.clairo.com.au` | CNAME | `cname.vercel-dns.com` | Frontend |
| `clairo.com.au` | A | Vercel IP | Apex domain redirect |
| `api.clairo.com.au` | CNAME | Railway/Fly.io domain | Backend API |
| clairo.com.au (Resend) | TXT/CNAME | Resend DNS records | Email sending |
