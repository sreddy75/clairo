# Implementation Plan: Beta Legal & Compliance

**Branch**: `052-beta-legal-compliance` | **Date**: 2026-04-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `/specs/052-beta-legal-compliance/spec.md`

## Summary

Make Clairo legally and operationally ready for beta launch. Add ToS acceptance gating (all users must accept before accessing the app), standardize AI disclaimers across all output screens, complete audit trail coverage for AI suggestions and human overrides, polish the landing page for credibility, and add cookie consent for analytics gating. Leverages existing `AuditService` infrastructure, Clerk auth flow, and Next.js App Router patterns.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Anthropic SDK, React 18 + shadcn/ui, Clerk (auth), PostHog (analytics), Sentry (error tracking)
**Storage**: PostgreSQL 16 (3 new columns on existing `users` table, no new tables)
**Testing**: pytest + pytest-asyncio (backend), ESLint + tsc (frontend)
**Target Platform**: Web — accountant SaaS platform
**Project Type**: Web (backend + frontend)
**Performance Goals**: ToS acceptance adds < 1s to login flow. Audit logging adds < 50ms per AI call.
**Constraints**: Legal page content is placeholder until legal drafting is complete. Cookie consent must not break Sentry error tracking.
**Scale/Scope**: ~10 tenants at beta launch, ~50 users, ~500 AI calls/day

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith structure | PASS | No new modules needed. Extends existing auth, tax_planning, bas, insights modules. Admin audit endpoint added to existing admin routes. |
| Repository pattern | PASS | Audit queries via existing `AuditService`. ToS update via existing `User` repository. |
| Multi-tenancy | PASS | Audit log viewer scoped to `tenant_id`. ToS is per-user (not tenant-scoped). Legal pages are public. |
| Tech stack compliance | PASS | Python 3.12, FastAPI, SQLAlchemy 2.0, React 18, shadcn/ui, Clerk |
| Audit events | PASS | This feature *is* the audit completion story. 11 new event types defined. |
| Testing strategy | PASS | Unit tests for ToS service logic, integration tests for audit endpoints |
| API design standards | PASS | RESTful routes, Pydantic schemas |
| Human-in-the-loop | PASS | Human override logging (approve/modify/reject) is a core deliverable |
| No financial advice | PASS | AI disclaimer explicitly states this is not tax advice |

## Project Structure

### Documentation (this feature)

```text
specs/052-beta-legal-compliance/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research output
├── data-model.md        # Phase 1 data model
├── quickstart.md        # Developer quickstart
├── contracts/
│   └── api.md           # API endpoint contracts
├── checklists/
│   └── requirements.md  # Quality checklist
└── tasks.md             # Phase 2 output (via /speckit.tasks)
```

### Source Code (repository root)

```text
backend/app/
├── core/
│   └── constants.py                    # AI_DISCLAIMER_TEXT, TOS_CURRENT_VERSION
├── modules/
│   ├── auth/
│   │   ├── models.py                   # +3 columns on User
│   │   ├── router.py                   # +2 endpoints (accept-terms, tos-version)
│   │   ├── service.py                  # +accept_terms() method
│   │   └── schemas.py                  # +ToS fields in bootstrap response
│   ├── tax_planning/
│   │   ├── service.py                  # +AuditService calls
│   │   ├── audit_events.py             # NEW
│   │   └── agents/orchestrator.py      # +AuditService calls
│   ├── bas/
│   │   ├── tax_code_service.py         # +AuditService calls
│   │   └── audit_events.py             # NEW (AI-specific events)
│   ├── insights/
│   │   ├── service.py                  # +AuditService calls
│   │   └── analyzers/ai_analyzer.py    # +AuditService calls
│   └── admin/
│       ├── router.py                   # NEW: audit list/export/summary
│       └── schemas.py                  # NEW: response schemas
└── alembic/versions/
    └── xxx_add_tos_fields.py           # +3 columns to users

frontend/src/
├── app/
│   ├── accept-terms/page.tsx           # NEW: ToS gate page
│   ├── terms/page.tsx                  # NEW: Legal page
│   ├── privacy/page.tsx                # NEW: Legal page
│   ├── acceptable-use/page.tsx         # NEW: Legal page
│   ├── not-found.tsx                   # NEW: 404 page
│   ├── layout.tsx                      # +OG tags, conditional analytics
│   ├── page.tsx                        # +footer polish, trust statement
│   └── (protected)/
│       ├── layout.tsx                  # +ToS check in bootstrap
│       └── admin/audit/page.tsx        # NEW: Audit viewer
├── components/
│   ├── ui/AIDisclaimer.tsx             # NEW: Shared disclaimer
│   └── CookieConsentBanner.tsx         # NEW: Cookie banner
├── hooks/
│   └── useCookieConsent.ts             # NEW: Consent state
└── lib/
    ├── analytics.tsx                   # +consent gating
    └── constants.ts                    # NEW: shared constants
```

**Structure Decision**: No new modules. All backend changes extend existing modules (auth, tax_planning, bas, insights). The admin audit viewer is a new page in the existing admin section. Frontend adds 5 new pages and 3 new components.

## Key Reuse Opportunities

| Existing Component | Reuse For | Location |
|---|---|---|
| AuditService | All new audit event logging | `core/audit.py` |
| audit_logs table (immutable) | All new event types — no schema change | `alembic/versions/001_auth_multitenancy.py` |
| @audited decorator | Service method audit wrapping | `core/audit.py:457` |
| Bootstrap endpoint | ToS check — extend response | `auth/router.py` (GET /bootstrap) |
| Protected layout bootstrap | ToS redirect — add check | `(protected)/layout.tsx:231-277` |
| Onboarding flow | ToS page — same auth pattern | `onboarding/page.tsx` |
| Admin nav | Audit viewer nav entry | `(protected)/layout.tsx:75-80` |
| PostHog/Sentry integration | Cookie consent gating | `lib/analytics.tsx` |
| Landing page footer | Legal links, ABN, email | `page.tsx:888-932` |

## Implementation Phases

### Phase 1: ToS Gate & Legal Pages (US1)
- Alembic migration: 3 columns on `users` table
- Backend: `core/constants.py` with `TOS_CURRENT_VERSION`
- Backend: `POST /accept-terms` endpoint + `accept_terms()` service method
- Backend: `GET /tos-version` endpoint
- Backend: Extend bootstrap response with ToS fields
- Frontend: `/accept-terms` page (Clerk auth required, shadcn/ui form)
- Frontend: ToS check in protected layout bootstrap
- Frontend: Legal pages at `/terms`, `/privacy`, `/acceptable-use` (shared layout, placeholder content)
- Frontend: Fix footer links across all layouts (landing, auth, protected)
- Frontend: Custom 404 page

### Phase 2: AI Disclaimers (US2)
- Backend: `AI_DISCLAIMER_TEXT` constant in `core/constants.py`
- Frontend: `AIDisclaimer.tsx` component (shadcn/ui `Alert` variant)
- Frontend: `constants.ts` with shared disclaimer text
- Replace 4 ad-hoc disclaimer instances with shared component/constant
- Add disclaimer to BAS review/preparation screens (currently missing)
- Add disclaimer to client portal views (currently missing)
- Update PDF export templates to use backend constant

### Phase 3: Audit Trail Completeness (US3)
- Create `audit_events.py` in tax_planning and bas modules
- Add `AuditService.log_event()` to tax planning service (chat + streaming)
- Add `AuditService.log_event()` to multi-agent orchestrator (per sub-agent)
- Add `AuditService.log_event()` to BAS tax code service (LLM + client classification)
- Add `AuditService.log_event()` to insights service + AI analyzer
- Add human override logging (approve/modify/reject) to tax code resolution flow
- Backend: Admin audit endpoints (list, export CSV, summary)
- Frontend: `/admin/audit` page with filters, pagination, CSV export button

### Phase 4: Landing Page Polish (US4)
- Add OG meta tags to root layout (title, description, image, type)
- Add social share image (static asset)
- Update footer: ABN, contact email, legal page links
- Verify/add favicon sizes (16x16, 32x32, apple-touch-icon)
- Mobile responsive audit and fixes (375px minimum)
- Add security/trust statement section
- Verify "How it works" section content
- Add pricing placeholder or "Contact us" CTA

### Phase 5: Cookie Consent (US5)
- `useCookieConsent` hook (localStorage-based)
- `CookieConsentBanner` component (shadcn/ui)
- Modify `analytics.tsx` to check consent before loading PostHog + Speed Insights
- Sentry remains unconditional (legitimate interest)
- Link to cookie policy in banner

## Complexity Tracking

No constitution violations. All changes extend existing infrastructure (audit service, auth module, admin section). No new database tables, no new external dependencies, no cross-module boundary violations.
