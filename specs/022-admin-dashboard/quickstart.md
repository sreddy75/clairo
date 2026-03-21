# Quickstart: Admin Dashboard (Internal)

**Feature Branch**: `feature/022-admin-dashboard`
**Created**: 2026-01-01

## Prerequisites

- Python 3.12+
- Node.js 20+
- Docker Compose (for local development)
- Admin role in the system (`is_admin=True` on PracticeUser)

## Quick Start

### 1. Backend Setup

```bash
# Switch to feature branch
git checkout feature/022-admin-dashboard

# Install dependencies
cd backend
uv sync

# Run migrations (after models are created)
uv run alembic upgrade head

# Start backend
docker-compose up -d
```

### 2. Frontend Setup

```bash
# Install dependencies
cd frontend
npm install

# Start development server
npm run dev
```

### 3. Access Admin Dashboard

Navigate to: `http://localhost:3000/internal/admin`

**Note**: You must be logged in with an admin account.

## Project Structure

### Backend

```
backend/app/modules/admin/
├── __init__.py          # Module exports
├── router.py            # API endpoints (extended from Spec 020)
├── service.py           # AdminDashboardService (new)
├── repository.py        # AdminRepository (new)
├── models.py            # FeatureFlagOverride (new)
├── schemas.py           # Request/Response models (extended)
├── exceptions.py        # AdminError hierarchy (new)
└── usage_service.py     # Existing usage service
```

### Frontend

```
frontend/src/app/(protected)/internal/admin/
├── layout.tsx           # Admin layout with sidebar
├── page.tsx             # Dashboard overview
├── customers/
│   ├── page.tsx         # Tenant list
│   └── [id]/
│       └── page.tsx     # Tenant detail
├── revenue/
│   └── page.tsx         # Revenue metrics
└── components/
    ├── TenantTable.tsx
    ├── RevenueMetrics.tsx
    ├── TierChangeModal.tsx
    ├── CreditModal.tsx
    └── FeatureFlagOverrides.tsx
```

## Key Files

### Backend

| File | Purpose |
|------|---------|
| `models.py` | `FeatureFlagOverride` SQLAlchemy model |
| `repository.py` | Database operations for tenants, overrides, billing events |
| `service.py` | Business logic: tier changes, credits, revenue metrics |
| `router.py` | FastAPI endpoints under `/api/v1/admin/` |
| `schemas.py` | Pydantic request/response models |

### Frontend

| File | Purpose |
|------|---------|
| `layout.tsx` | Admin-only layout with navigation |
| `page.tsx` | Dashboard overview with key metrics |
| `customers/page.tsx` | Searchable, filterable tenant list |
| `customers/[id]/page.tsx` | Comprehensive tenant detail view |
| `revenue/page.tsx` | MRR, churn, expansion charts |

## API Endpoints

### Tenant Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/tenants` | List all tenants (paginated) |
| GET | `/admin/tenants/{id}` | Get tenant details |

### Revenue Analytics

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/revenue/metrics` | MRR, churn, expansion |
| GET | `/admin/revenue/trends` | Historical trends |

### Subscription Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| PATCH | `/admin/tenants/{id}/tier` | Change subscription tier |
| POST | `/admin/tenants/{id}/credits` | Apply credit |

### Feature Flags

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/tenants/{id}/feature-flags` | Get all flags |
| PUT | `/admin/tenants/{id}/feature-flags/{key}` | Set override |
| DELETE | `/admin/tenants/{id}/feature-flags/{key}` | Remove override |

## Testing

### Backend Unit Tests

```bash
cd backend
uv run pytest tests/unit/modules/admin/ -v
```

### Backend Integration Tests

```bash
cd backend
uv run pytest tests/integration/api/test_admin.py -v
```

### Frontend Tests

```bash
cd frontend
npm run test
```

## Environment Variables

No new environment variables required. Uses existing:

```bash
# Stripe (for tier changes and credits)
STRIPE_SECRET_KEY=sk_test_...

# Redis (for revenue metrics caching)
REDIS_URL=redis://localhost:6379/0
```

## Common Operations

### Create an Admin User (Dev)

```python
# In Python shell
from app.modules.auth.models import PracticeUser
from app.database import AsyncSession

async with AsyncSession() as session:
    user = await session.get(PracticeUser, user_id)
    user.is_admin = True
    await session.commit()
```

### Test Revenue Metrics

```bash
curl -X GET "http://localhost:8000/api/v1/admin/revenue/metrics" \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

### Change Tenant Tier

```bash
curl -X PATCH "http://localhost:8000/api/v1/admin/tenants/{tenant_id}/tier" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_tier": "professional",
    "reason": "Upgrade for trial period"
  }'
```

## Troubleshooting

### "Forbidden" when accessing admin dashboard

- Ensure your user has `is_admin=True`
- Check JWT token is valid and not expired
- Verify the `require_admin()` dependency is working

### Revenue metrics not loading

- Check Stripe API key is valid
- Verify Redis is running for caching
- Check backend logs for Stripe API errors

### Tier change fails

- Verify tenant has a Stripe subscription
- Check Stripe webhook is configured
- Look for "pending" billing events in logs

## Development Workflow

1. **Backend changes**: Make changes in `backend/app/modules/admin/`
2. **Run tests**: `uv run pytest tests/unit/modules/admin/ -v`
3. **Check types**: `uv run mypy app/modules/admin/`
4. **Frontend changes**: Make changes in `frontend/src/app/(protected)/internal/admin/`
5. **Run linting**: `npm run lint`

## Related Documentation

- [Spec 020: Usage Tracking](../020-usage-tracking/spec.md) - Existing admin usage endpoints
- [Spec 019: Subscription Feature Gating](../019-subscription-feature-gating/spec.md) - Stripe integration
- [Constitution](../../.specify/memory/constitution.md) - Development standards
