# Quickstart: Usage Tracking & Limits

**Date**: 2025-12-31
**Feature**: 020-usage-tracking

---

## Prerequisites

1. **Spec 019 Complete**: Billing module with tiers must be in place
2. **Docker Compose Running**: `docker-compose up -d`
3. **Database Migrated**: All migrations up to 024 applied
4. **Test User**: Authenticated user with a tenant

---

## Quick Test Scenarios

### Scenario 1: View Usage Dashboard

**Goal**: Verify usage dashboard displays correctly

```bash
# 1. Get auth token
TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "test@example.com", "password": "password123"}' \
  | jq -r '.access_token')

# 2. Get usage metrics
curl -s http://localhost:8000/api/v1/billing/usage \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Expected Response**:
```json
{
  "client_count": 12,
  "client_limit": 100,
  "client_percentage": 12.0,
  "ai_queries_month": 45,
  "documents_month": 23,
  "is_at_limit": false,
  "is_approaching_limit": false,
  "threshold_warning": null,
  "tier": "professional",
  "next_tier": "growth"
}
```

---

### Scenario 2: Client Limit Enforcement

**Goal**: Verify clients cannot be added when at limit

```bash
# 1. Set up a Starter tier tenant at 25 clients (limit)
# (Use test fixtures or manually add 25 XeroConnections)

# 2. Try to add another client via Xero sync
curl -X POST http://localhost:8000/api/v1/xero/sync \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json"

# OR try to manually add client
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"xero_contact_id": "new-contact-id"}'
```

**Expected Response (403)**:
```json
{
  "error": "Client limit reached",
  "code": "CLIENT_LIMIT_EXCEEDED",
  "details": {
    "current_count": 25,
    "limit": 25,
    "upgrade_tier": "professional",
    "upgrade_url": "/pricing"
  }
}
```

---

### Scenario 3: Threshold Alert Email

**Goal**: Verify email sent at 80% threshold

```bash
# 1. Set up a Starter tier tenant with 19 clients (76%)
# 2. Add one more client to reach 20 (80%)

# Monitor email logs or mailhog (dev email catcher)
docker-compose logs -f mailhog

# Add 20th client
curl -X POST http://localhost:8000/api/v1/clients \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"xero_contact_id": "client-20"}'
```

**Expected**:
- Client added successfully
- Email sent to tenant owner
- Email subject: "You're at 80% of your client limit"

---

### Scenario 4: Usage History

**Goal**: Verify historical usage data retrieval

```bash
# Get 3 months of usage history
curl -s "http://localhost:8000/api/v1/billing/usage/history?months=3" \
  -H "Authorization: Bearer $TOKEN" | jq
```

**Expected Response**:
```json
{
  "snapshots": [
    {
      "id": "uuid-1",
      "captured_at": "2025-12-01T00:00:00Z",
      "client_count": 10,
      "ai_queries_count": 150,
      "documents_count": 45,
      "tier": "professional",
      "client_limit": 100
    },
    {
      "id": "uuid-2",
      "captured_at": "2025-11-01T00:00:00Z",
      "client_count": 8,
      "ai_queries_count": 120,
      "documents_count": 38,
      "tier": "professional",
      "client_limit": 100
    }
  ],
  "period_start": "2025-10-01T00:00:00Z",
  "period_end": "2025-12-31T00:00:00Z"
}
```

---

### Scenario 5: Admin Usage Analytics

**Goal**: Verify admin can view aggregate stats

```bash
# Login as admin
ADMIN_TOKEN=$(curl -s -X POST http://localhost:8000/api/v1/admin/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "admin@clairo.ai", "password": "admin123"}' \
  | jq -r '.access_token')

# Get aggregate stats
curl -s http://localhost:8000/api/v1/admin/usage/stats \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

**Expected Response**:
```json
{
  "total_tenants": 150,
  "total_clients": 4500,
  "average_clients_per_tenant": 30.0,
  "tenants_at_limit": 5,
  "tenants_approaching_limit": 12,
  "tenants_by_tier": {
    "starter": 80,
    "professional": 50,
    "growth": 15,
    "enterprise": 5
  }
}
```

---

### Scenario 6: Upsell Opportunities

**Goal**: Verify admin can identify upsell candidates

```bash
# Get tenants at >=80% of limit
curl -s "http://localhost:8000/api/v1/admin/usage/opportunities?threshold=80" \
  -H "Authorization: Bearer $ADMIN_TOKEN" | jq
```

**Expected Response**:
```json
{
  "opportunities": [
    {
      "tenant_id": "uuid-1",
      "tenant_name": "Smith & Associates",
      "owner_email": "john@smithassociates.com.au",
      "current_tier": "starter",
      "client_count": 23,
      "client_limit": 25,
      "percentage_used": 92.0
    }
  ],
  "total": 1
}
```

---

## Frontend Test Scenarios

### Scenario 7: Usage Dashboard UI

**Steps**:
1. Login to app at http://localhost:3000
2. Navigate to Settings → Billing
3. Scroll to "Usage" section

**Expected**:
- Progress bar showing "Clients: X / Y"
- Color coding based on percentage
- AI queries and documents counts
- "View History" link

---

### Scenario 8: In-App Alert Banner

**Setup**: Tenant at >=80% of client limit

**Steps**:
1. Login as tenant at 80%+ usage
2. View any page with header

**Expected**:
- Yellow/orange banner at top
- Message: "You're at X% of your client limit"
- "Upgrade" button linking to pricing

---

### Scenario 9: Limit Reached Error

**Setup**: Tenant at 100% of client limit

**Steps**:
1. Login as tenant at limit
2. Try to add new client via Xero sync

**Expected**:
- Error modal appears
- Message: "You've reached your X client limit"
- "Upgrade to Y" button with next tier pricing
- Option to disconnect existing clients

---

## Database Verification

```sql
-- Check usage snapshots
SELECT * FROM usage_snapshots
WHERE tenant_id = 'your-tenant-uuid'
ORDER BY captured_at DESC
LIMIT 5;

-- Check usage alerts
SELECT * FROM usage_alerts
WHERE tenant_id = 'your-tenant-uuid'
ORDER BY sent_at DESC;

-- Check tenant usage fields
SELECT
  name,
  tier,
  client_count,
  ai_queries_month,
  documents_month,
  usage_month_reset
FROM tenants
WHERE id = 'your-tenant-uuid';
```

---

## Troubleshooting

### Emails Not Sending

```bash
# Check mailhog UI
open http://localhost:8025

# Check email service logs
docker-compose logs backend | grep -i email

# Verify SES credentials (production)
aws ses get-send-statistics
```

### Client Count Mismatch

```bash
# Recalculate client count
curl -X POST http://localhost:8000/api/v1/billing/usage/recalculate \
  -H "Authorization: Bearer $TOKEN"

# Check XeroConnection count directly
SELECT COUNT(*) FROM xero_connections
WHERE tenant_id = 'your-uuid'
AND status != 'disconnected';
```

### Snapshot Job Not Running

```bash
# Check celery beat
docker-compose logs celery-beat

# Manually trigger snapshot
curl -X POST http://localhost:8000/api/v1/admin/usage/snapshot \
  -H "Authorization: Bearer $ADMIN_TOKEN"
```

---

## Integration Points

| System | Integration | Notes |
|--------|-------------|-------|
| Xero Sync | Increment client count after sync | Check limits before adding |
| Chat Endpoint | Increment ai_queries_month | On successful completion |
| Document Upload | Increment documents_month | On processing complete |
| Celery Beat | Daily snapshots at midnight UTC | Configured in celerybeat schedule |
| Email Service | AWS SES for alerts | Uses owner_email from tenant |
