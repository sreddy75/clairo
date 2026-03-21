# Research: Usage Tracking & Limits

**Date**: 2025-12-31
**Feature**: 020-usage-tracking

---

## Research Topics

### 1. Existing Infrastructure Analysis

**Topic**: What usage tracking already exists from Spec 019?

**Findings**:
- `Tenant.client_count` field exists (integer, default 0)
- `BillingService.get_usage_info()` method calculates:
  - `client_count`: Current count from tenant
  - `client_limit`: From tier configuration
  - `is_at_limit`: Boolean (count >= limit)
  - `is_approaching_limit`: Boolean (percentage >= 80)
  - `percentage_used`: Float percentage
- `UsageInfo` schema already defined with above fields
- `get_client_limit(tier)` helper in `feature_flags.py`
- `ClientLimitExceededError` exception exists

**Decision**: Build on existing infrastructure rather than replace it.

**Implications**:
- New models extend billing module
- Existing UsageInfo schema needs enhancement for AI queries and documents
- Client count logic already works - just need to ensure it stays in sync

---

### 2. Email Infrastructure

**Topic**: What email sending capability exists?

**Findings**:
- ✅ **EmailService exists** at `backend/app/modules/notifications/email_service.py`
- Uses **Resend** library for transactional emails
- Already has templating support via `EmailTemplates`
- Configuration in `settings.resend` (api_key, from_email, reply_to, enabled)
- Existing email types: welcome, team_invitation, password_reset, bas_reminder, lodgement_confirmation

**Decision**: Extend existing EmailService with usage alert templates

**Rationale**:
- Infrastructure already in place
- Consistent with existing email patterns
- Resend handles delivery, tracking, templates
- Already configured and tested

**Implementation**:
```python
# Add to backend/app/modules/notifications/templates.py
@classmethod
def usage_threshold_alert(
    cls,
    user_name: str,
    percentage: int,
    client_count: int,
    client_limit: int,
    tier: str,
    upgrade_url: str,
) -> EmailTemplate:
    """Generate usage threshold alert email."""
    return EmailTemplate(
        subject=f"You're at {percentage}% of your client limit",
        html=f"...",
        text=f"...",
    )

# Add to EmailService
async def send_usage_threshold_alert(
    self,
    to: str,
    user_name: str,
    percentage: int,
    client_count: int,
    client_limit: int,
    tier: str,
    upgrade_url: str = "https://app.clairo.ai/pricing",
) -> str | None:
    """Send usage threshold alert email."""
    template = self.templates.usage_threshold_alert(
        user_name=user_name,
        percentage=percentage,
        client_count=client_count,
        client_limit=client_limit,
        tier=tier,
        upgrade_url=upgrade_url,
    )
    return await self.send_email(
        to=to,
        template=template,
        tags=[
            {"name": "category", "value": "usage"},
            {"name": "type", "value": f"threshold_{percentage}"},
        ],
    )
```

**No new infrastructure needed** - just add templates and service methods

---

### 3. Background Job System

**Topic**: How to implement daily usage snapshots?

**Findings**:
- Celery + Redis configured in docker-compose
- `backend/app/tasks/` directory exists for background tasks
- Celery beat can schedule periodic tasks

**Decision**: Use Celery beat for daily snapshot job at midnight UTC

**Implementation**:
```python
# backend/app/tasks/usage_tasks.py
from celery import shared_task

@shared_task
def capture_daily_usage_snapshots():
    """Capture usage snapshots for all tenants."""
    # Query all tenants, create UsageSnapshot for each
    ...

# celerybeat schedule
CELERYBEAT_SCHEDULE = {
    'daily-usage-snapshots': {
        'task': 'app.tasks.usage_tasks.capture_daily_usage_snapshots',
        'schedule': crontab(hour=0, minute=0),  # Midnight UTC
    },
}
```

---

### 4. AI Query Counting

**Topic**: How to track AI queries per tenant?

**Findings**:
- Chat endpoints exist in agents module
- No current tracking of query volume
- Need to count chat completions per tenant per month

**Decision**: Add counter increment in chat endpoint, store monthly total in tenant

**Implementation approaches**:

| Approach | Pros | Cons |
|----------|------|------|
| Increment counter on each request | Simple, real-time | Potential race conditions |
| Redis atomic counter | Fast, atomic | Need redis key management |
| Database counter with transaction | ACID compliant | Slightly slower |

**Selected**: Database counter with `UPDATE tenants SET ai_queries_month = ai_queries_month + 1`

**Rationale**: ACID compliance more important than speed for billing-relevant data

---

### 5. Document Processing Counting

**Topic**: How to track documents processed?

**Findings**:
- Document upload exists in documents module
- OCR processing tracked per document
- Need to count uploads per tenant per month

**Decision**: Increment counter when document processing completes successfully

**Location**: Hook into document processing completion event

---

### 6. Usage Dashboard Patterns

**Topic**: Best practices for usage visualization

**Findings**:
- Industry standard: Progress bars with percentage
- Color coding: Green (<60%), Yellow (60-79%), Orange (80-89%), Red (>=90%)
- Common metrics: Used / Limit format
- Upgrade prompts at threshold crossings

**Decision**: Follow SaaS industry patterns with clear visual hierarchy

**Reference designs**:
- Stripe Dashboard usage section
- GitHub Actions usage
- AWS service limits

---

### 7. Alert Deduplication

**Topic**: How to prevent duplicate alerts?

**Findings**:
- Need to track which alerts have been sent per tenant
- Alerts should reset each billing period
- Both 80% and 90% thresholds need tracking independently

**Decision**: Store alerts in `usage_alerts` table with:
- `tenant_id`
- `threshold_type` (80 or 90)
- `billing_period` (YYYY-MM format)
- `sent_at`

**Query before sending**:
```sql
SELECT 1 FROM usage_alerts
WHERE tenant_id = :tenant_id
  AND threshold_type = :threshold
  AND billing_period = :period
```

---

## Technology Decisions Summary

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Email service | Resend (existing) | Already configured in notifications module |
| Background jobs | Celery beat | Already configured, proven |
| AI query tracking | Database counter | ACID compliance |
| Alert deduplication | Database table | Persistent, queryable |
| Snapshot frequency | Daily | Balance of granularity and storage |
| Usage visualization | Progress bars | Industry standard |

---

## Open Questions Resolved

| Question | Answer |
|----------|--------|
| Where to store monthly AI queries? | New field on Tenant: `ai_queries_month` |
| Where to store monthly documents? | New field on Tenant: `documents_month` |
| When to reset monthly counters? | Background job on 1st of each month |
| How to handle timezone? | Use UTC for all snapshots and periods |

---

## No Further Clarifications Needed

All technical decisions have been made with clear rationale. Ready for Phase 1 (data-model.md, contracts).
