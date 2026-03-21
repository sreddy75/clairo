# Implementation Plan: Onboarding Flow

**Branch**: `021-onboarding-flow` | **Date**: 2025-12-31 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/021-onboarding-flow/spec.md`

---

## Summary

Create a guided onboarding experience that takes new accountants from Clerk signup through tier selection, Stripe checkout (with 14-day trial), Xero/XPM connection, bulk client import, and product tour to first value. This is the final piece of Phase D (Monetization Foundation) before Pilot Launch.

**Key Components**:
1. **Signup Flow**: Clerk auth → tier selection → Stripe trial checkout
2. **Trial Management**: 14-day trial with reminders and auto-conversion
3. **Xero/XPM Connection**: OAuth flow with XPM detection
4. **Bulk Client Import**: Multi-select with background processing
5. **Product Tour**: Interactive walkthrough (5-7 steps)
6. **Onboarding Checklist**: Persistent progress widget
7. **Welcome Emails**: Drip sequence via Resend

---

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x (frontend)
**Primary Dependencies**:
- Backend: FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery, Stripe SDK
- Frontend: Next.js 14 (App Router), React 18, TailwindCSS, shadcn/ui, React Hook Form, Zustand
**Storage**: PostgreSQL 16 (with existing schema), Redis (Celery broker)
**Testing**: pytest + pytest-asyncio (backend), Jest + Playwright (frontend)
**Target Platform**: Web application (desktop + mobile responsive)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Onboarding completion in <15 minutes, bulk import progress updates <2s latency
**Constraints**: Australian data residency (Sydney region), Stripe AU, Xero AU
**Scale/Scope**: Initial target 50 practices, ~5,000 clients

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Status | Notes |
|-----------|--------|-------|
| Modular Monolith | PASS | New `onboarding` module follows existing pattern |
| Repository Pattern | PASS | All DB access via repositories |
| Module Boundaries | PASS | Cross-module calls via service layer only |
| Technology Stack | PASS | Using approved stack (FastAPI, Next.js, etc.) |
| Multi-tenancy | PASS | tenant_id on all new tables, RLS enforced |
| Audit-First | PASS | Audit events defined for all onboarding steps |
| Testing Requirements | PASS | Will include unit + integration tests |
| Layer Compliance | PASS | Phase D (Monetization) - on track |

**All gates passed.**

---

## Project Structure

### Documentation (this feature)

```text
specs/021-onboarding-flow/
├── spec.md              # Feature specification (complete)
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Developer quickstart
├── contracts/           # API contracts
│   └── openapi.yaml     # OpenAPI spec for onboarding endpoints
├── checklists/          # Quality checklists
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Implementation tasks (Phase 2)
```

### Source Code (repository root)

```text
backend/
├── app/
│   ├── modules/
│   │   ├── onboarding/          # NEW MODULE
│   │   │   ├── __init__.py
│   │   │   ├── models.py        # OnboardingProgress, BulkImportJob
│   │   │   ├── schemas.py       # Pydantic schemas
│   │   │   ├── repository.py    # Database access
│   │   │   ├── service.py       # Business logic
│   │   │   ├── router.py        # API endpoints
│   │   │   ├── events.py        # Audit events
│   │   │   └── tasks.py         # Celery tasks (bulk import, emails)
│   │   │
│   │   ├── billing/             # EXTEND (trial support)
│   │   │   └── service.py       # Add trial creation logic
│   │   │
│   │   ├── integrations/xero/   # EXTEND (XPM support)
│   │   │   ├── xpm_client.py    # NEW: XPM API client
│   │   │   └── service.py       # Add XPM client fetching
│   │   │
│   │   └── notifications/       # EXTEND (welcome emails)
│   │       └── templates/       # Email templates
│   │           ├── welcome.html
│   │           ├── trial_reminder.html
│   │           └── onboarding_nudge.html
│   │
│   └── tasks/
│       └── onboarding_tasks.py  # Celery task definitions
│
└── tests/
    ├── unit/modules/onboarding/
    └── integration/api/test_onboarding.py

frontend/
├── src/
│   ├── app/
│   │   ├── onboarding/          # NEW: Onboarding flow pages
│   │   │   ├── page.tsx         # Entry point (redirects to correct step)
│   │   │   ├── tier-selection/
│   │   │   │   └── page.tsx     # Tier selection + trial start
│   │   │   ├── connect-xero/
│   │   │   │   └── page.tsx     # Xero/XPM OAuth
│   │   │   ├── import-clients/
│   │   │   │   └── page.tsx     # Bulk import UI
│   │   │   └── layout.tsx       # Onboarding layout (progress indicator)
│   │   │
│   │   └── (dashboard)/
│   │       └── layout.tsx       # EXTEND: Add tour + checklist
│   │
│   ├── components/
│   │   ├── onboarding/          # NEW: Onboarding components
│   │   │   ├── TierCard.tsx
│   │   │   ├── ClientImportList.tsx
│   │   │   ├── ImportProgress.tsx
│   │   │   ├── OnboardingChecklist.tsx
│   │   │   └── ProductTour.tsx
│   │   │
│   │   └── ui/                  # Extend shadcn components as needed
│   │
│   ├── hooks/
│   │   ├── useOnboarding.ts     # Onboarding state + progress
│   │   └── useTour.ts           # Product tour state
│   │
│   └── lib/
│       └── api/
│           └── onboarding.ts    # API client functions
│
└── tests/
    └── e2e/onboarding.spec.ts   # Playwright E2E tests
```

**Structure Decision**: Web application pattern with backend `onboarding` module + frontend `onboarding` app route. Follows existing modular monolith architecture.

---

## Dependencies

### Existing Modules (Dependencies)

| Module | Used For | Integration Point |
|--------|----------|-------------------|
| `auth` | Tenant creation, user management | `TenantService.create()` |
| `billing` | Stripe subscriptions, trial management | `BillingService.create_trial_subscription()` |
| `integrations/xero` | Xero OAuth, data sync | `XeroService.connect()`, `XeroService.sync_clients()` |
| `clients` | Client creation from Xero data | `ClientService.create_from_xero()` |
| `notifications` | Email sending | `NotificationService.send_email()` |

### New External Dependencies

| Dependency | Purpose | Notes |
|------------|---------|-------|
| `react-joyride` | Product tour library | Interactive step-by-step tours |
| Xero Practice Manager API | XPM client list | Requires XPM OAuth scope |

---

## Key Technical Decisions

### 1. Onboarding State Machine

```
STARTED → TIER_SELECTED → PAYMENT_SETUP → XERO_CONNECTED → CLIENTS_IMPORTED → TOUR_COMPLETED → COMPLETED
                                              ↓ (skip)
                                         SKIPPED_XERO
```

Each state is persisted in `OnboardingProgress` table. Users can resume from any step.

### 2. Bulk Import Architecture

```
User selects clients → POST /api/onboarding/import → Create BulkImportJob
                                                            ↓
                                                    Celery task starts
                                                            ↓
                                                    For each client:
                                                      - Fetch from XPM/Xero
                                                      - Create client record
                                                      - Queue transaction sync
                                                      - Update job progress
                                                            ↓
                                                    WebSocket/SSE for progress
                                                            ↓
                                                    Job completes → summary
```

### 3. Trial Implementation

- Stripe `subscription.trial_end` set to 14 days from creation
- `trial_ends_at` stored on Tenant for quick access
- Celery beat task checks daily for trial expiration reminders
- Webhook handles `customer.subscription.trial_will_end` and `invoice.payment_failed`

### 4. XPM Detection

```python
# In XeroService
async def detect_connection_type(self, tenant_id: UUID) -> str:
    """Detect if tenant has XPM or standard Xero."""
    # Check OAuth scopes for practice.clients
    # If present, return "xpm"
    # Else return "xero_accounting"
```

---

## Complexity Tracking

No constitution violations requiring justification.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| XPM API rate limits during bulk import | Medium | Medium | Exponential backoff, batch processing |
| Stripe webhook delivery failure | Low | High | Idempotent processing, retry logic |
| User abandons during onboarding | High | Medium | Save progress, recovery emails |
| Xero OAuth token expires mid-import | Low | Medium | Token refresh handling, resume capability |

---

## Success Metrics (from Spec)

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Signup to payment completion | <5 min | Timestamp diff |
| Xero connection rate | >70% | OnboardingProgress analysis |
| First client import rate | >60% | OnboardingProgress analysis |
| Time to first value | <15 min | Timestamp diff |
| Checklist completion (7 days) | >50% | OnboardingProgress analysis |
| Trial-to-paid conversion | >25% | Stripe subscription analysis |

---

## Next Steps

1. **Phase 0**: Generate `research.md` with XPM API details, tour library evaluation
2. **Phase 1**: Generate `data-model.md`, `contracts/openapi.yaml`, `quickstart.md`
3. **Phase 2**: Generate `tasks.md` via `/speckit.tasks`
4. **Implementation**: Execute tasks with TDD approach
