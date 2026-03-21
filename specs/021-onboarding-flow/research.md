# Research: Onboarding Flow

**Feature**: 021-onboarding-flow
**Date**: 2025-12-31
**Status**: Complete

---

## Research Topics

1. Xero Practice Manager (XPM) API for client list
2. Product tour library selection
3. Stripe trial subscription implementation
4. Email drip sequence patterns
5. Bulk import with progress tracking

---

## 1. Xero Practice Manager (XPM) API

### Decision
Use Xero Practice Manager API with `practice.clients` scope to fetch practice client list for bulk import.

### Rationale
- XPM is the standard practice management tool for Australian accounting firms
- XPM "Clients" represent the businesses an accountant manages (our target entity)
- Xero Accounting "Contacts" are entities within a single organization (fallback only)

### XPM API Details

**Endpoint**: `GET https://api.xero.com/practicemanager.xro/3.0/clients`

**Required OAuth Scopes**:
```
practice.clients.read
```

**Response Structure**:
```json
{
  "Clients": [
    {
      "ClientID": "guid",
      "Name": "Acme Pty Ltd",
      "Email": "contact@acme.com.au",
      "Phone": "02 1234 5678",
      "Address": "123 Main St, Sydney NSW 2000",
      "TaxNumber": "12345678901",
      "ClientGroupID": "guid",
      "Status": "Active"
    }
  ]
}
```

**Rate Limits**:
- 60 calls per minute per tenant
- For bulk operations: batch requests, exponential backoff

### Detection Logic
```python
# Check if XPM scopes are authorized
xpm_scopes = ["practice.clients.read", "practice.settings.read"]
has_xpm = any(scope in connection.scopes for scope in xpm_scopes)
```

### Fallback: Xero Accounting Contacts
If XPM is not available, use Xero Contacts API:
- `GET /api.xro/2.0/Contacts`
- Filter by `IsCustomer=true` for business clients

### Alternatives Considered
| Option | Pros | Cons |
|--------|------|------|
| XPM API only | Clean data model | Excludes non-XPM users |
| Xero Contacts only | Universal | Contacts ≠ Clients semantically |
| **Both with detection** | Best coverage | Slightly more complex |

**Selected**: Both with automatic detection

---

## 2. Product Tour Library

### Decision
Use `react-joyride` for interactive product tours.

### Rationale
- Most popular React tour library (2.5M weekly downloads)
- Declarative step definitions
- Spotlight/overlay effects
- Good accessibility support
- Active maintenance

### Implementation Pattern
```tsx
import Joyride, { Step } from 'react-joyride';

const tourSteps: Step[] = [
  {
    target: '.dashboard-header',
    content: 'Welcome to Clairo! This is your dashboard overview.',
    placement: 'bottom',
  },
  {
    target: '.client-list',
    content: 'View and manage all your clients here.',
    placement: 'right',
  },
  // ... 5-7 steps total
];

function Dashboard() {
  const [runTour, setRunTour] = useState(false);

  return (
    <>
      <Joyride
        steps={tourSteps}
        run={runTour}
        continuous
        showProgress
        showSkipButton
        callback={handleTourCallback}
      />
      {/* Dashboard content */}
    </>
  );
}
```

### Tour Steps (5-7)
1. Dashboard overview
2. Client list & search
3. BAS workflow status
4. Data quality scores
5. AI insights panel
6. Settings & billing
7. Help & support (optional)

### Alternatives Considered
| Library | Stars | Bundle Size | Notes |
|---------|-------|-------------|-------|
| **react-joyride** | 5.8k | 45kb | Most flexible, best docs |
| shepherd.js | 12k | 92kb | Framework-agnostic, larger |
| react-tour | 1.8k | 15kb | Simpler, less customizable |
| intro.js | 22k | 35kb | Not React-native |

**Selected**: react-joyride

---

## 3. Stripe Trial Subscription

### Decision
Use Stripe's native trial feature with `trial_period_days` parameter.

### Rationale
- Stripe handles trial expiration automatically
- Automatic conversion to paid on trial end
- Built-in webhooks for trial events
- No custom date tracking needed

### Implementation Pattern

**Create subscription with trial**:
```python
subscription = stripe.Subscription.create(
    customer=stripe_customer_id,
    items=[{"price": price_id}],
    trial_period_days=14,
    payment_behavior="default_incomplete",
    expand=["latest_invoice.payment_intent"],
)
```

**Key webhook events**:
- `customer.subscription.trial_will_end` - 3 days before trial ends
- `customer.subscription.updated` - Trial converts to active
- `invoice.payment_failed` - First charge after trial fails

### Trial State Storage
```python
# On Tenant model (already exists in auth/models.py)
trial_ends_at: datetime | None  # From Stripe subscription
subscription_status: SubscriptionStatus  # TRIAL, ACTIVE, etc.
```

### Trial Reminder Logic
```python
# Celery beat task - daily at 9am AEDT
@celery.task
def check_trial_reminders():
    # Find trials ending in 3 days
    three_days = datetime.now(UTC) + timedelta(days=3)
    tenants = TenantRepository.find_trials_ending_before(three_days)

    for tenant in tenants:
        if not has_sent_reminder(tenant, "3_day"):
            send_trial_reminder_email(tenant, days_remaining=3)
            mark_reminder_sent(tenant, "3_day")
```

### Alternatives Considered
| Approach | Pros | Cons |
|----------|------|------|
| **Stripe native trial** | Automatic, reliable | Limited customization |
| Custom trial tracking | Full control | More code, edge cases |
| Delayed subscription | Simple | No real "trial" experience |

**Selected**: Stripe native trial

---

## 4. Email Drip Sequence

### Decision
Use Resend with Celery scheduled tasks for email automation.

### Rationale
- Resend already integrated (Spec 019-020)
- Celery beat for scheduling
- Template storage in `notifications/templates/`
- Transactional emails, not marketing (ACMA compliant)

### Email Sequence
| Trigger | Timing | Template | Purpose |
|---------|--------|----------|---------|
| Signup complete | Immediate | `welcome.html` | Welcome, next steps |
| No Xero connection | +24h | `connect_xero.html` | Encourage connection |
| No clients imported | +48h | `import_clients.html` | Prompt import |
| Mid-trial | Day 7 | `trial_midpoint.html` | Feature highlights |
| Trial ending | Day 12 | `trial_ending.html` | Conversion push |
| Onboarding complete | On completion | `onboarding_complete.html` | Celebrate, tips |

### Implementation Pattern
```python
# Track sent emails
class EmailDrip(Base):
    __tablename__ = "email_drips"

    tenant_id: UUID
    email_type: str  # "welcome", "connect_xero", etc.
    sent_at: datetime

    # Unique constraint prevents duplicates
    __table_args__ = (
        UniqueConstraint("tenant_id", "email_type"),
    )

# Celery task
@celery.task
def send_onboarding_drip_emails():
    # Find tenants who need nudge emails
    for tenant in find_incomplete_onboarding_tenants():
        if should_send_drip(tenant, "connect_xero"):
            send_email(tenant.email, "connect_xero")
            record_drip_sent(tenant, "connect_xero")
```

### Alternatives Considered
| Approach | Pros | Cons |
|----------|------|------|
| **Resend + Celery** | Already integrated | Manual scheduling |
| Customer.io | Full marketing automation | Additional cost, complexity |
| Mailchimp | Powerful automation | Overkill for transactional |

**Selected**: Resend + Celery (existing infrastructure)

---

## 5. Bulk Import with Progress Tracking

### Decision
Use Celery tasks with database-backed progress tracking, polled via REST API.

### Rationale
- Celery already in stack for background processing
- Database progress tracking allows resume-ability
- REST polling simpler than WebSocket for MVP
- Can upgrade to SSE/WebSocket later if needed

### Implementation Pattern

**BulkImportJob Model**:
```python
class BulkImportJobStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    PARTIAL_FAILURE = "partial_failure"
    FAILED = "failed"

class BulkImportJob(Base):
    __tablename__ = "bulk_import_jobs"

    id: UUID
    tenant_id: UUID
    status: BulkImportJobStatus
    total_clients: int
    imported_count: int
    failed_count: int
    failed_clients: list[dict]  # JSONB
    started_at: datetime
    completed_at: datetime | None
    progress_percent: int  # Computed
```

**Celery Task**:
```python
@celery.task(bind=True, max_retries=3)
def bulk_import_clients(self, job_id: UUID, client_ids: list[str]):
    job = BulkImportJobRepository.get(job_id)
    job.status = BulkImportJobStatus.IN_PROGRESS

    for i, client_id in enumerate(client_ids):
        try:
            import_single_client(job.tenant_id, client_id)
            job.imported_count += 1
        except Exception as e:
            job.failed_count += 1
            job.failed_clients.append({"id": client_id, "error": str(e)})

        # Update progress every 5 clients
        if i % 5 == 0:
            job.progress_percent = int((i + 1) / len(client_ids) * 100)
            BulkImportJobRepository.update(job)

    job.status = (
        BulkImportJobStatus.COMPLETED if job.failed_count == 0
        else BulkImportJobStatus.PARTIAL_FAILURE
    )
    job.completed_at = datetime.now(UTC)
    BulkImportJobRepository.update(job)
```

**Frontend Polling**:
```typescript
function useImportProgress(jobId: string) {
  return useQuery({
    queryKey: ['import-job', jobId],
    queryFn: () => api.getImportJob(jobId),
    refetchInterval: (data) =>
      data?.status === 'in_progress' ? 2000 : false,
  });
}
```

### Progress Update Frequency
- Database update: Every 5 clients
- Frontend poll: Every 2 seconds while in_progress
- Expected import time: ~30s per client (Xero API + data processing)

### Alternatives Considered
| Approach | Pros | Cons |
|----------|------|------|
| **Celery + polling** | Simple, reliable | Slight delay |
| WebSocket | Real-time | Complexity, connection management |
| Server-Sent Events | Real-time, simpler | Connection limits |
| Celery result backend | Built-in | Less flexible |

**Selected**: Celery + REST polling (MVP), can upgrade to SSE later

---

## Summary of Decisions

| Topic | Decision | Key Reasoning |
|-------|----------|---------------|
| XPM Integration | XPM API with Xero fallback | Best client data source for accounting firms |
| Product Tour | react-joyride | Most popular, flexible, good React integration |
| Trial Subscriptions | Stripe native trial | Automatic handling, built-in webhooks |
| Email Drips | Resend + Celery | Existing infrastructure, simple scheduling |
| Bulk Import Progress | Celery + REST polling | Reliable, simple, upgradeable |

---

## Open Questions (Resolved)

All research questions have been resolved. No outstanding items.

---

## References

- [Xero Practice Manager API](https://developer.xero.com/documentation/api/practicemanager/overview)
- [react-joyride Documentation](https://react-joyride.com/)
- [Stripe Subscriptions with Trials](https://stripe.com/docs/billing/subscriptions/trials)
- [Resend Email API](https://resend.com/docs/introduction)
