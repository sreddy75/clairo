# Quickstart: Onboarding Flow

**Feature**: 021-onboarding-flow
**Date**: 2025-12-31

---

## Prerequisites

1. **Backend running**: `docker-compose up -d`
2. **Frontend running**: `cd frontend && npm run dev`
3. **Stripe CLI**: For webhook testing `stripe listen --forward-to localhost:8000/api/v1/billing/webhooks`
4. **Xero Developer Account**: For OAuth testing

---

## Quick Setup

### 1. Run Database Migration

```bash
cd backend
uv run alembic upgrade head
```

### 2. Install Frontend Dependencies

```bash
cd frontend
npm install react-joyride
```

### 3. Configure Environment

Ensure these are set in `.env`:

```bash
# Stripe (test keys)
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...
STRIPE_WEBHOOK_SECRET=whsec_...

# Stripe Price IDs (create in Stripe dashboard)
STRIPE_PRICE_STARTER=price_...
STRIPE_PRICE_PROFESSIONAL=price_...
STRIPE_PRICE_GROWTH=price_...

# Xero
XERO_CLIENT_ID=...
XERO_CLIENT_SECRET=...
XERO_REDIRECT_URI=http://localhost:3000/onboarding/xero/callback

# Email (Resend)
RESEND_API_KEY=re_...
RESEND_FROM_EMAIL=Clairo <noreply@clairo.ai>
```

---

## Testing the Flow

### Manual Testing

1. **Start Onboarding**
   - Create new account via Clerk
   - Verify redirect to `/onboarding/tier-selection`

2. **Select Tier**
   - Choose Professional tier
   - Verify Stripe Checkout opens with $0.00 trial

3. **Complete Payment Setup**
   - Use test card `4242 4242 4242 4242`
   - Verify redirect to Connect Xero step

4. **Connect Xero**
   - Click Connect Xero
   - Complete OAuth flow
   - Verify organization name displayed

5. **Import Clients**
   - View client list from XPM/Xero
   - Select multiple clients
   - Start import
   - Verify progress updates

6. **Product Tour**
   - Complete or skip tour
   - Verify checklist updates

### API Testing

```bash
# Get onboarding progress
curl -X GET http://localhost:8000/api/v1/onboarding/progress \
  -H "Authorization: Bearer $TOKEN"

# Start bulk import
curl -X POST http://localhost:8000/api/v1/onboarding/clients/import \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"client_ids": ["client-1", "client-2"]}'

# Check import progress
curl -X GET http://localhost:8000/api/v1/onboarding/import/{job_id} \
  -H "Authorization: Bearer $TOKEN"
```

---

## Key Files

### Backend

| File | Purpose |
|------|---------|
| `app/modules/onboarding/models.py` | Data models |
| `app/modules/onboarding/service.py` | Business logic |
| `app/modules/onboarding/router.py` | API endpoints |
| `app/modules/onboarding/tasks.py` | Celery tasks |

### Frontend

| File | Purpose |
|------|---------|
| `app/onboarding/page.tsx` | Onboarding entry point |
| `app/onboarding/tier-selection/page.tsx` | Tier selection |
| `app/onboarding/import-clients/page.tsx` | Bulk import UI |
| `components/onboarding/ProductTour.tsx` | Tour component |
| `components/onboarding/OnboardingChecklist.tsx` | Checklist widget |

---

## Common Issues

### Stripe Checkout Not Opening

- Check `STRIPE_PUBLISHABLE_KEY` is set
- Verify price IDs are correct
- Ensure trial prices are configured in Stripe

### Xero OAuth Failing

- Check redirect URI matches Xero app settings
- Verify XPM scopes are enabled if using XPM
- Check OAuth callback handling

### Import Not Progressing

- Check Celery worker is running: `celery -A app.tasks worker --loglevel=info`
- Check Redis connection
- Review Celery logs for errors

### Tour Not Showing

- Check `react-joyride` is installed
- Verify tour steps target valid DOM elements
- Check `useTour` hook initialization

---

## Development Tips

1. **Skip onboarding for testing**:
   ```python
   # In tests/conftest.py
   @pytest.fixture
   def completed_onboarding_tenant(tenant):
       # Set onboarding as complete for testing other features
       progress = OnboardingProgress(
           tenant_id=tenant.id,
           status=OnboardingStatus.COMPLETED,
           completed_at=datetime.now(UTC),
       )
       db.add(progress)
       db.commit()
       return tenant
   ```

2. **Mock Xero in tests**:
   ```python
   @pytest.fixture
   def mock_xero_clients():
       with patch("app.modules.integrations.xero.service.XeroService.get_xpm_clients") as mock:
           mock.return_value = [
               {"ClientID": "1", "Name": "Test Client 1"},
               {"ClientID": "2", "Name": "Test Client 2"},
           ]
           yield mock
   ```

3. **Test trial expiration**:
   ```python
   # Manually set trial end date in past
   tenant.trial_ends_at = datetime.now(UTC) - timedelta(days=1)
   db.commit()
   # Run trial check task
   check_trial_reminders()
   ```

---

## Verification Checklist

- [ ] New user is redirected to onboarding after signup
- [ ] Tier selection shows all tiers with correct pricing
- [ ] Stripe Checkout opens with 14-day trial
- [ ] Payment completion updates onboarding progress
- [ ] Xero OAuth connects successfully
- [ ] XPM clients are listed for import
- [ ] Bulk import shows progress
- [ ] Failed imports can be retried
- [ ] Product tour launches on first dashboard visit
- [ ] Tour can be skipped and restarted
- [ ] Onboarding checklist shows correct progress
- [ ] Checklist can be dismissed
- [ ] Welcome email is sent on signup
- [ ] Trial reminder emails are sent at correct times
