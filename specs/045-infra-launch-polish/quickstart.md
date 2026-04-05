# Quickstart: Infra & Launch Polish

**Date**: 2026-04-06

## Production Deployment Steps

### 1. Provision Backend (Railway)

1. Create Railway project at https://railway.app
2. Connect GitHub repo (sreddy75/clairo)
3. Add service → Docker → point to `backend/Dockerfile.prod`
4. Configure:
   - Root directory: `backend`
   - Region: closest to Sydney (or auto)
   - Start command: (uses Dockerfile CMD)
5. Add all backend env vars from `contracts/infrastructure.md`
6. Generate a public domain → note as `api.clairo.com.au` target

### 2. Provision Database (Railway Postgres)

1. In Railway project → Add service → PostgreSQL
2. Get connection string
3. Connect as superuser → run `scripts/create_production_role.sql`
4. Run migrations: `alembic upgrade head` (via Railway CLI or deploy)
5. Update `DATABASE_URL` to use `clairo_app` role (not superuser)

### 3. Provision Redis (Upstash)

1. Create account at https://upstash.com
2. Create Redis database → region: ap-southeast (Singapore/closest to AU)
3. Get connection URL
4. Set as `REDIS_URL` in Railway

### 4. Provision Object Storage (Cloudflare R2)

1. Create R2 bucket at Cloudflare dashboard
2. Create API token with R2 read/write
3. Set `MINIO_ENDPOINT`, `MINIO_ACCESS_KEY`, `MINIO_SECRET_KEY`, `MINIO_USE_SSL=true`

### 5. Deploy Frontend (Vercel)

1. Import project at https://vercel.com/new
2. Framework: Next.js
3. Root directory: `frontend`
4. Set all frontend env vars from `contracts/infrastructure.md`
5. Deploy → note preview URL

### 6. Configure DNS

1. In domain registrar for clairo.com.au:
   - `www` → CNAME → `cname.vercel-dns.com`
   - `@` → A record → Vercel IP (from Vercel domains page)
   - `api` → CNAME → Railway public domain
2. In Vercel → Domains → add `clairo.com.au` and `www.clairo.com.au`
3. Wait for SSL auto-provisioning (usually <10 minutes)

### 7. Production Credentials

1. **Clerk**: Create production instance → copy `sk_live_*` and `pk_live_*` → set in Railway + Vercel
2. **Stripe**: Switch to live mode → create product/price ($299 AUD) → register webhook endpoint `https://api.clairo.com.au/api/v1/billing/webhooks/stripe` → copy `whsec_*` secret → set in Railway
3. **Sentry**: Create project → copy DSN → set `SENTRY_DSN` in Railway + Vercel
4. **Xero**: Update redirect URI to `https://www.clairo.com.au/settings/integrations/xero/callback`

### 8. Verify

- [ ] https://clairo.com.au loads landing page
- [ ] https://api.clairo.com.au/health returns healthy
- [ ] Sign up works (no "Development mode" banner)
- [ ] Onboarding completes (trial subscription created in Stripe live)
- [ ] Dashboard loads with real data
- [ ] Sentry captures a test error
- [ ] Email sends from noreply@clairo.com.au
- [ ] Rate limiting works (20 req/min on auth endpoints)
- [ ] RLS enforced (non-superuser DB role)
