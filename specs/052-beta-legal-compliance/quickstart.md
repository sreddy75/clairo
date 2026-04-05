# Quickstart: Beta Legal & Compliance

**Branch**: `052-beta-legal-compliance` | **Date**: 2026-04-05

## Prerequisites

- Docker Compose running (PostgreSQL, Redis)
- Backend: `cd backend && uv sync`
- Frontend: `cd frontend && npm install`

## What Changes

### Backend

```
backend/app/
├── core/
│   └── constants.py                    # NEW: AI_DISCLAIMER_TEXT, TOS_CURRENT_VERSION
├── modules/
│   ├── auth/
│   │   ├── models.py                   # MODIFIED: Add tos_accepted_at, tos_version_accepted, tos_accepted_ip to User
│   │   ├── router.py                   # MODIFIED: Add POST /accept-terms, GET /tos-version; extend bootstrap response
│   │   ├── service.py                  # MODIFIED: accept_terms() method
│   │   └── schemas.py                  # MODIFIED: Add ToS fields to bootstrap response schema
│   ├── tax_planning/
│   │   ├── service.py                  # MODIFIED: Add AuditService calls after AI chat
│   │   ├── audit_events.py             # NEW: TAX_PLANNING_AUDIT_EVENTS
│   │   └── agents/orchestrator.py      # MODIFIED: Add AuditService calls per sub-agent
│   ├── bas/
│   │   ├── tax_code_service.py         # MODIFIED: Add AuditService calls after LLM classification
│   │   └── audit_events.py             # NEW: BAS_AUDIT_EVENTS (AI-specific)
│   ├── insights/
│   │   ├── service.py                  # MODIFIED: Add AuditService calls after AI summarization
│   │   └── analyzers/ai_analyzer.py    # MODIFIED: Add AuditService calls after AI analysis
│   └── admin/
│       ├── __init__.py                 # NEW: Admin module for audit viewer
│       ├── router.py                   # NEW: GET /admin/audit, GET /admin/audit/export, GET /admin/audit/summary
│       └── schemas.py                  # NEW: AuditLogResponse, AuditSummaryResponse
└── alembic/versions/
    └── xxx_add_tos_fields.py           # NEW: Migration adding 3 columns to users table
```

### Frontend

```
frontend/src/
├── app/
│   ├── accept-terms/page.tsx           # NEW: ToS acceptance page (public, requires Clerk auth)
│   ├── terms/page.tsx                  # NEW: Terms of Service legal page
│   ├── privacy/page.tsx                # NEW: Privacy Policy legal page
│   ├── acceptable-use/page.tsx         # NEW: Acceptable Use Policy legal page
│   ├── not-found.tsx                   # NEW: Custom 404 page
│   ├── layout.tsx                      # MODIFIED: Add OG meta tags; conditional analytics loading
│   ├── page.tsx                        # MODIFIED: Footer (ABN, email, legal links); trust statement
│   └── (protected)/
│       ├── layout.tsx                  # MODIFIED: ToS check in bootstrap; add audit nav item
│       └── admin/audit/page.tsx        # NEW: Audit log viewer
├── components/
│   ├── ui/AIDisclaimer.tsx             # NEW: Shared AI disclaimer component
│   └── CookieConsentBanner.tsx         # NEW: Cookie consent banner
├── hooks/
│   └── useCookieConsent.ts             # NEW: Cookie consent state hook
└── lib/
    ├── analytics.tsx                   # MODIFIED: Gate PostHog/SpeedInsights behind consent
    └── constants.ts                    # NEW: AI_DISCLAIMER_TEXT, TOS_VERSION
```

## Database Migration

```bash
cd backend && uv run alembic revision --autogenerate -m "Add ToS acceptance fields to users"
cd backend && uv run alembic upgrade head
```

Adds 3 columns to `users` table: `tos_accepted_at`, `tos_version_accepted`, `tos_accepted_ip`. All nullable — existing users will see the ToS acceptance prompt on next login.

## Key Development Steps

1. **Backend constants + migration** — Create `core/constants.py` with ToS version and disclaimer text. Run migration for User model columns.
2. **ToS acceptance flow** — Backend: `accept_terms()` service method + router endpoint. Frontend: `/accept-terms` page, bootstrap check in protected layout.
3. **Legal pages** — Build `/terms`, `/privacy`, `/acceptable-use` as static pages with shared layout. Fix dead footer links.
4. **AI disclaimer component** — Create `AIDisclaimer.tsx`, replace all 4 ad-hoc instances, add to missing screens (BAS, portal).
5. **Audit event types** — Create `audit_events.py` in tax_planning and bas modules. Add `AuditService.log_event()` calls to all AI service methods.
6. **Audit admin viewer** — Backend: query/export endpoints. Frontend: `/admin/audit` page with filters and CSV export.
7. **Landing page polish** — OG tags, ABN, contact email, 404 page, mobile audit, trust statement.
8. **Cookie consent** — `useCookieConsent` hook, `CookieConsentBanner` component, gate analytics in `analytics.tsx`.

## Running

```bash
# Backend
cd backend && uv run uvicorn app.main:app --reload

# Frontend
cd frontend && npm run dev

# Test ToS flow
# 1. Sign up as new user — should see ToS acceptance before dashboard
# 2. As existing user (tos_accepted_at=null) — should redirect to /accept-terms
# 3. Accept terms — should proceed to dashboard

# Test cookie consent
# 1. Open in incognito — should see cookie banner
# 2. Open browser DevTools > Network — no PostHog requests until Accept
# 3. Click Accept — PostHog loads, banner disappears
# 4. Reload — no banner, PostHog loads automatically

# Test audit log
# 1. Generate a tax plan (triggers AI audit events)
# 2. Visit /admin/audit — should see the events
# 3. Click Export CSV — verify data matches
```

## Validation

```bash
# Backend
cd backend && uv run ruff check . && uv run pytest

# Frontend
cd frontend && npm run lint && npx tsc --noEmit
```
