# Implementation Plan: Client Portal Foundation + Document Requests

**Branch**: `030-client-portal-document-requests` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/030-client-portal-document-requests/spec.md`

## Summary

Build the client portal enabling business owners to view BAS status and respond to document requests, plus implement ClientChase document request workflow with templates, bulk sending, tracking, and auto-reminders.

**Technical Approach**:
- Create new `portal` module for client-facing functionality
- Magic link authentication (JWT tokens, no passwords)
- Separate portal Next.js route group
- Integrate with existing documents and notifications modules

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, Celery
**Storage**: PostgreSQL 16, S3/MinIO
**Email**: Resend
**Testing**: pytest, pytest-asyncio
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Portal <2s load, bulk requests <30s for 100 clients
**Constraints**: No password for clients, magic link only
**Scale/Scope**: Support 10,000 clients across tenants

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | New `portal` module |
| **Repository Pattern** | ✅ PASS | Dedicated repositories |
| **Multi-tenancy (RLS)** | ✅ PASS | Portal scoped to client's tenant |
| **Audit-First** | ✅ PASS | All portal actions audited |
| **Type Hints** | ✅ PASS | Pydantic schemas throughout |
| **Test-First** | ✅ PASS | Test magic link, requests, uploads |
| **API Conventions** | ✅ PASS | RESTful endpoints |
| **Privacy** | ✅ PASS | Client only sees their data |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/030-client-portal-document-requests/
├── plan.md              # This file
├── research.md          # Portal and ClientChase research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   ├── portal-api.yaml        # Client-facing API
│   └── request-api.yaml       # Accountant request API
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── portal/                      # NEW MODULE
│           ├── __init__.py
│           ├── models.py                # Portal entities
│           ├── schemas.py               # Request/response schemas
│           ├── repository.py            # Database operations
│           ├── service.py               # Business logic
│           │
│           ├── auth/                    # Magic link auth
│           │   ├── __init__.py
│           │   ├── magic_link.py        # Token generation/verification
│           │   ├── router.py            # Auth endpoints
│           │   └── dependencies.py      # get_current_client
│           │
│           ├── dashboard/               # Client dashboard
│           │   ├── __init__.py
│           │   ├── service.py           # Dashboard aggregation
│           │   └── router.py            # Dashboard endpoints
│           │
│           ├── requests/                # Document requests (ClientChase)
│           │   ├── __init__.py
│           │   ├── models.py            # Request entities
│           │   ├── templates.py         # Built-in templates
│           │   ├── service.py           # Request logic
│           │   ├── router.py            # Request endpoints (accountant)
│           │   └── client_router.py     # Request endpoints (client)
│           │
│           ├── documents/               # Portal document upload
│           │   ├── __init__.py
│           │   ├── upload.py            # Upload handling
│           │   └── router.py            # Upload endpoints
│           │
│           └── notifications/           # Email notifications
│               ├── __init__.py
│               ├── templates.py         # Email templates
│               └── reminders.py         # Auto-reminder logic
│
├── tasks/
│   └── portal/
│       ├── send_invitations.py          # Batch invitation sending
│       └── auto_reminders.py            # Daily reminder job
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── portal/
    │           ├── test_magic_link.py
    │           ├── test_request_service.py
    │           └── test_auto_filing.py
    └── integration/
        └── api/
            ├── test_portal_auth.py
            └── test_document_requests.py

frontend/
└── src/
    ├── app/
    │   ├── (protected)/                 # Accountant app
    │   │   └── clients/
    │   │       └── [id]/
    │   │           └── requests/        # Request management
    │   │               ├── page.tsx
    │   │               └── new/page.tsx
    │   │
    │   └── portal/                      # CLIENT PORTAL (new route group)
    │       ├── layout.tsx               # Portal layout
    │       ├── page.tsx                 # Dashboard
    │       ├── auth/
    │       │   ├── login/page.tsx       # Request magic link
    │       │   └── verify/page.tsx      # Verify magic link
    │       ├── requests/
    │       │   ├── page.tsx             # Request list
    │       │   └── [id]/page.tsx        # Request detail + respond
    │       └── documents/
    │           └── page.tsx             # Document library
    │
    ├── components/
    │   ├── portal/
    │   │   ├── PortalHeader.tsx
    │   │   ├── DashboardCards.tsx
    │   │   ├── RequestCard.tsx
    │   │   ├── RespondForm.tsx
    │   │   └── DocumentUploader.tsx
    │   │
    │   └── requests/                    # Accountant components
    │       ├── RequestTemplateSelector.tsx
    │       ├── BulkRequestWizard.tsx
    │       ├── RequestTrackingTable.tsx
    │       └── RequestStatusBadge.tsx
    │
    └── lib/
        └── api/
            ├── portal.ts                # Client portal API
            └── requests.ts              # Request management API
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    CLIENT PORTAL ARCHITECTURE                            │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    ACCOUNTANT PORTAL                               │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │   Invite    │  │  Templates  │  │   Tracking  │               │ │
│  │  │   Client    │  │  & Bulk     │  │  Dashboard  │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         │                │                │                        │ │
│  │         ▼                ▼                ▼                        │ │
│  │  ┌───────────────────────────────────────────────────────────┐    │ │
│  │  │              DOCUMENT REQUEST SERVICE                      │    │ │
│  │  │  - Create requests (single/bulk)                          │    │ │
│  │  │  - Track status                                            │    │ │
│  │  │  - Auto-reminders                                          │    │ │
│  │  └───────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                  │                                      │
│                    Email (Magic Link + Notifications)                   │
│                                  │                                      │
│                                  ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                      CLIENT PORTAL                                 │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │  Dashboard  │  │  Requests   │  │  Documents  │               │ │
│  │  │  BAS Status │  │  Respond &  │  │  Upload     │               │ │
│  │  │  Metrics    │  │  Upload     │  │  Library    │               │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │ │
│  │                          │                                         │ │
│  │                          ▼                                         │ │
│  │  ┌───────────────────────────────────────────────────────────┐    │ │
│  │  │              DOCUMENT UPLOAD SERVICE                       │    │ │
│  │  │  - Drag-drop upload                                        │    │ │
│  │  │  - Mobile camera capture                                   │    │ │
│  │  │  - Auto-filing by type/period                             │    │ │
│  │  └───────────────────────────────────────────────────────────┘    │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Request Workflow

```
DOCUMENT REQUEST WORKFLOW (ClientChase)
═══════════════════════════════════════════════════════════════════════════

ACCOUNTANT SIDE                           CLIENT SIDE
───────────────────────────────────────────────────────────────────────────

1. CREATE REQUEST
   ├── Select template or custom
   ├── Set due date
   ├── Choose clients (1 or bulk)
   └── Send
                │
                ▼
2. NOTIFICATION SENT                      3. CLIENT RECEIVES
   ├── Email with link                    ├── Email notification
   └── Push notification                   └── Portal shows new request
                                                      │
                                                      ▼
                                           4. CLIENT VIEWS
                                              └── Status → VIEWED
                                                      │
                                                      ▼
                                           5. CLIENT RESPONDS
                                              ├── Upload documents
                                              ├── Add note
                                              └── Submit
                │                                     │
                ▼                                     ▼
6. ACCOUNTANT NOTIFIED                     Status → RESPONDED
   ├── Email notification
   └── Dashboard updated
                │
                ▼
7. REVIEW & COMPLETE
   ├── Review documents
   ├── Request more if needed
   └── Mark complete
                │
                ▼
   Status → COMPLETE

AUTO-REMINDERS (Parallel Process)
───────────────────────────────────────────────────────────────────────────
Daily job checks all PENDING requests:
- 3 days before due → Reminder email
- 1 day before due → Urgent reminder
- Overdue → Daily overdue reminder (up to 7 days)
```

### Magic Link Authentication Flow

```
MAGIC LINK AUTHENTICATION
═══════════════════════════════════════════════════════════════════════════

1. ACCOUNTANT INVITES
   POST /api/v1/clients/{id}/invite
   └── Generate magic link token (7-day expiry)
   └── Send invitation email
                │
                ▼
2. CLIENT CLICKS LINK
   GET /portal/auth/verify?token=xxx
   └── Verify JWT token
   └── Check not expired
   └── Create portal session
   └── Redirect to dashboard
                │
                ▼
3. SESSION MANAGEMENT
   ├── Short-lived access token (1 hour)
   └── Long-lived refresh token (30 days)

4. RETURN VISIT
   GET /portal/auth/login
   └── Enter email
   └── Send new magic link
   └── Same verification flow
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Auth Method | Magic Link (JWT) | No password friction, secure enough for portal |
| Token Expiry | 7 days | Balance security with convenience |
| Bulk Request | Individual records | Better tracking, per-client customization |
| Auto-Reminders | Daily Celery job | Reliable, timezone-aware scheduling |
| File Storage | S3/MinIO | Scalable, already in stack |
| Auto-Filing | Request-based tagging | Documents linked to request context |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Magic link token theft | Short expiry, single-use option, IP validation |
| Email delivery failures | Resend retry, bounce tracking, fallback options |
| Large file uploads | Client-side compression, chunked upload, size limits |
| Bulk request performance | Background processing, batch DB operations |
| Client confusion | Clear onboarding email, simple UI, help content |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Clients module | Required | Client records to invite |
| Documents module | Required | Document storage |
| Notifications module | Required | Email sending |
| BAS module | Required | BAS status for dashboard |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| Resend | - | Email delivery |
| AWS S3 | - | Document storage |
| PyJWT | 2.8+ | Magic link tokens |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for portal research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/portal-api.yaml](./contracts/portal-api.yaml) for client API
- **Phase 1**: See [contracts/request-api.yaml](./contracts/request-api.yaml) for accountant API
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
