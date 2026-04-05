# Tasks: Beta Legal & Compliance

**Input**: Design documents from `/specs/052-beta-legal-compliance/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not explicitly requested in spec. Test tasks omitted.

**Organization**: Tasks grouped by user story for independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup

- [ ] T000 Create feature branch `052-beta-legal-compliance` from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b 052-beta-legal-compliance`
  - _Already done — verify you are on the branch_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Shared constants and database migration that multiple user stories depend on

- [x] T001 Create shared constants file with ToS version and AI disclaimer text in `backend/app/core/constants.py`
  - Define `TOS_CURRENT_VERSION = "1.0"`, `TOS_EFFECTIVE_DATE = "2026-04-01"`, `AI_DISCLAIMER_TEXT = "This is AI-assisted decision support for registered tax agents. It does not constitute tax advice. Professional judgement should always be applied."`
- [x] T002 [P] Create shared frontend constants file in `frontend/src/lib/constants.ts`
  - Export `AI_DISCLAIMER_TEXT` (same wording as backend) and `TOS_VERSION`
- [x] T003 Create Alembic migration adding ToS fields to users table in `backend/alembic/versions/`
  - Add 3 columns to `users`: `tos_accepted_at` (TIMESTAMPTZ, nullable), `tos_version_accepted` (VARCHAR(20), nullable), `tos_accepted_ip` (INET, nullable)
  - Run: `cd backend && uv run alembic revision --autogenerate -m "Add ToS acceptance fields to users"`
  - Run: `cd backend && uv run alembic upgrade head`
- [x] T004 Update User model with ToS fields in `backend/app/modules/auth/models.py`
  - Add `tos_accepted_at: Mapped[datetime | None]`, `tos_version_accepted: Mapped[str | None]`, `tos_accepted_ip: Mapped[str | None]` to the `User` class (~line 415)

**Checkpoint**: Constants defined, migration applied, User model updated

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend ToS service logic and auth schema changes that US1 frontend depends on

- [x] T005 Add ToS fields to bootstrap response schema in `backend/app/modules/auth/schemas.py`
  - Add `tos_accepted_at: datetime | None` and `tos_version_accepted: str | None` to the bootstrap user response schema
- [x] T006 Add `accept_terms()` method to auth service in `backend/app/modules/auth/service.py`
  - Accept `user_id`, `version`, `ip_address`. Set `tos_accepted_at`, `tos_version_accepted`, `tos_accepted_ip` on the User. Log audit event `user.tos.accepted` via `AuditService`.
- [x] T007 Add ToS endpoints to auth router in `backend/app/modules/auth/router.py`
  - `POST /api/v1/auth/accept-terms` — calls `accept_terms()`, returns updated ToS fields
  - `GET /api/v1/auth/tos-version` — returns `{version, effective_date}` from constants (public, no auth)
  - Extend the existing `GET /api/v1/auth/bootstrap` response to include ToS fields from the User model
- [x] T008 Add `/accept-terms` to public routes in `frontend/src/middleware.ts`
  - Add `/accept-terms` to the public/onboarding route matcher so Clerk-authenticated users can reach it without a backend registration check

**Checkpoint**: Backend ToS API complete, middleware allows accept-terms route

---

## Phase 3: User Story 1 — Legal Pages & Terms Acceptance (Priority: P1)

**Goal**: All users must accept ToS before accessing the app. Legal pages render at `/terms`, `/privacy`, `/acceptable-use`.

**Independent Test**: Sign up as new user → see ToS gate before dashboard. Visit `/terms` → page renders. Existing user with null `tos_accepted_at` → redirected to accept-terms.

### Implementation

- [x] T009 [P] [US1] Build ToS acceptance page at `frontend/src/app/accept-terms/page.tsx`
  - Clerk-authenticated page. Show ToS summary, link to full `/terms` page. Checkbox: "I have read and accept the Terms of Service and Privacy Policy." Disabled "Continue" button until checked. On submit: call `POST /api/v1/auth/accept-terms`, then redirect to `/onboarding` (new users) or `/dashboard` (existing users).
- [x] T010 [P] [US1] Create shared legal page layout at `frontend/src/app/(legal)/layout.tsx`
  - Public layout (no auth). Clairo logo, back-to-home link, footer with legal links. Clean, readable typography for long-form content.
- [x] T011 [P] [US1] Build Terms of Service page at `frontend/src/app/(legal)/terms/page.tsx`
  - Static page with placeholder content clearly marked "Draft — final version coming soon." Include last-updated date, company name, section headings.
- [x] T012 [P] [US1] Build Privacy Policy page at `frontend/src/app/(legal)/privacy/page.tsx`
  - Same pattern as terms page. Placeholder content with section headings for data collection, use, retention, rights.
- [x] T013 [P] [US1] Build Acceptable Use Policy page at `frontend/src/app/(legal)/acceptable-use/page.tsx`
  - Same pattern as terms page. Placeholder content covering prohibited uses, AI output usage, data handling.
- [x] T014 [US1] Add ToS check to protected layout bootstrap in `frontend/src/app/(protected)/layout.tsx`
  - In the `bootstrap()` function (~line 252), after successful bootstrap response, check if `user.tos_accepted_at` is null or `user.tos_version_accepted !== TOS_VERSION`. If so, redirect to `/accept-terms`. Import `TOS_VERSION` from `lib/constants.ts`.
- [x] T015 [US1] Update footer links across all layouts
  - Landing page footer (`frontend/src/app/page.tsx` ~line 888): update existing `/terms` and `/privacy` links to use `(legal)` route group paths, add `/acceptable-use` link
  - Auth layout (`frontend/src/app/(auth)/layout.tsx` ~line 41): add legal links to footer
  - Protected layout: verify footer includes legal links (or add if missing)
- [x] T016 [US1] Build custom 404 page at `frontend/src/app/not-found.tsx`
  - Branded 404 page with Clairo logo, "Page not found" message, and link back to homepage. Use shadcn/ui components.

**Checkpoint**: ToS gate works for new and existing users. Legal pages render. 404 page works. All footers have legal links.

---

## Phase 4: User Story 2 — AI Disclaimers on All Outputs (Priority: P2)

**Goal**: Every screen showing AI-generated content displays a consistent disclaimer.

**Independent Test**: Visit tax plan view, BAS review, portal view, export PDF — all show identical disclaimer text.

### Implementation

- [x] T017 [P] [US2] Create shared AIDisclaimer component at `frontend/src/components/ui/AIDisclaimer.tsx`
  - Renders the standard disclaimer text from `lib/constants.ts`. Use shadcn/ui `Alert` component with `variant="default"` and an `Info` icon. Subtle styling — visible but not intrusive. Accept optional `className` prop for layout-specific spacing.
- [x] T018 [US2] Replace ad-hoc disclaimer in TaxPositionCard at `frontend/src/components/tax-planning/TaxPositionCard.tsx`
  - Replace inline disclaimer text (~line 124-126) with `<AIDisclaimer />` component.
- [x] T019 [P] [US2] Replace ad-hoc disclaimer in clipboard export at `frontend/src/lib/ai-export-utils.ts`
  - Replace hardcoded disclaimer strings (~line 28, 70-72) with imported `AI_DISCLAIMER_TEXT` from `lib/constants.ts`.
- [x] T020 [US2] Replace ad-hoc disclaimer in PDF export template at `backend/app/modules/tax_planning/templates/tax_plan_export.html`
  - Replace hardcoded disclaimer text (~line 155-159) with a Jinja2 variable `{{ ai_disclaimer }}` passed from the export route.
- [x] T021 [US2] Replace ad-hoc disclaimer in secondary PDF export at `backend/app/modules/tax_planning/router.py`
  - Replace inline HTML disclaimer (~line 756-762) with `AI_DISCLAIMER_TEXT` from `core/constants.py`.
- [x] T022 [US2] Pass disclaimer constant to PDF template context in `backend/app/modules/tax_planning/router.py`
  - Where the PDF template is rendered, add `ai_disclaimer=AI_DISCLAIMER_TEXT` to the template context dict.
- [x] T023 [US2] Add AIDisclaimer to BAS review/preparation screens
  - Identify all BAS-related pages in `frontend/src/app/(protected)/` that show AI-assisted content (tax code suggestions, classification results). Add `<AIDisclaimer />` component to each.
- [x] T024 [US2] Add AIDisclaimer to client portal views
  - Add `<AIDisclaimer />` to portal pages that display AI-generated content (tax plan view, BAS status). Check `frontend/src/app/portal/` for relevant pages.

**Checkpoint**: All AI output screens show identical disclaimer. PDF exports include disclaimer. No ad-hoc instances remain.

---

## Phase 5: User Story 3 — Audit Trail Completeness (Priority: P3)

**Goal**: All AI suggestions and human overrides are logged. Admin can view and export the audit log.

**Independent Test**: Generate a tax plan → check audit log → see AI event with model/tokens. Approve a tax code → see override event with before/after. Visit `/admin/audit` → see events, filter, export CSV.

### Implementation

- [x] T025 [P] [US3] Create tax planning audit events file at `backend/app/modules/tax_planning/audit_events.py`
  - Define `TAX_PLANNING_AUDIT_EVENTS` dict with event types: `ai.tax_planning.chat`, `ai.tax_planning.analysis`. Include category, description, retention.
- [x] T026 [P] [US3] Create BAS audit events file at `backend/app/modules/bas/audit_events.py`
  - Define `BAS_AI_AUDIT_EVENTS` dict with event types: `ai.bas.classification`, `ai.bas.client_classification`. Include category, description, retention. (Note: a `bas_audit_log` table exists for BAS session events — these new events go to the core `audit_logs` table for AI-specific calls.)
- [x] T027 [US3] Add AuditService calls to tax planning chat in `backend/app/modules/tax_planning/service.py`
  - After non-streaming AI chat (~line 840-854): log `ai.tax_planning.chat` with model, input_tokens, output_tokens, plan_id, scenarios_count in metadata.
  - After streaming chat (~line 963-1003): log at stream completion with token usage.
- [x] T028 [US3] Add AuditService calls to multi-agent orchestrator in `backend/app/modules/tax_planning/agents/orchestrator.py`
  - After each sub-agent call (~line 66-170): log `ai.tax_planning.analysis` with agent_role, model, input_tokens, output_tokens, plan_id in metadata.
- [x] T029 [US3] Add AuditService calls to BAS LLM classification in `backend/app/modules/bas/tax_code_service.py`
  - After `suggest_from_llm()` (~line 1079-1084): log `ai.bas.classification` with model, transaction_id (or hash), suggested_code, confidence, tier.
  - After `suggest_from_client_input()` (~line 1201-1203): log `ai.bas.client_classification` with model, classification_result.
- [x] T030 [US3] Add AuditService calls to insights AI analyzer in `backend/app/modules/insights/analyzers/ai_analyzer.py`
  - After AI analysis (~line 360-362): log `ai.insights.analysis` with model, analysis_type, input_tokens, output_tokens.
- [x] T031 [US3] Add AuditService calls to insights summarizer in `backend/app/modules/insights/service.py`
  - After AI summarization (~line 490-492): log `ai.insights.summary` with model, summary_length, input_tokens, output_tokens.
- [x] T032 [US3] Add human override audit logging to tax code resolution flow
  - Find where accountant approve/modify/reject actions are persisted (tax code suggestions or overrides). Add `AuditService.log_event()` calls logging `ai.suggestion.approved`, `ai.suggestion.modified`, or `ai.suggestion.rejected` with old_values (AI suggestion) and new_values (accountant's choice).
- [x] T033 [P] [US3] Create admin audit response schemas at `backend/app/modules/admin/schemas.py`
  - Create (or add to existing) admin schemas: `AuditLogListResponse` (paginated list), `AuditLogItem`, `AuditSummaryResponse`, `AuditExportParams`.
- [x] T034 [US3] Create admin audit router at `backend/app/modules/admin/router.py`
  - `GET /api/v1/admin/audit` — paginated, filterable audit log list (query params: page, per_page, event_type, event_category, actor_id, date_from, date_to, resource_type). Scoped to current tenant.
  - `GET /api/v1/admin/audit/export` — streaming CSV export with same filter params. Max 50,000 rows.
  - `GET /api/v1/admin/audit/summary` — aggregated stats (total events, by category, by type, AI suggestion approve/modify/reject counts).
  - Register router in `backend/app/main.py` if not already included.
- [x] T035 [US3] Build admin audit log viewer page at `frontend/src/app/(protected)/admin/audit/page.tsx`
  - Paginated table of audit events using shadcn/ui `Table`. Filters: date range (date picker), event type (select), event category (select), actor (search). Export CSV button. Summary cards at the top (total events, AI suggestions breakdown).
- [x] T036 [US3] Add audit log nav entry to admin navigation in `frontend/src/app/(protected)/layout.tsx`
  - Add `{ name: 'Audit Log', href: '/admin/audit', icon: ScrollText }` to the `adminNavigation` array (~line 75-80).
- [x] T037 [US3] Create API client functions for audit endpoints in `frontend/src/lib/api/admin.ts`
  - Add `fetchAuditLog()`, `fetchAuditSummary()`, `exportAuditCSV()` functions calling the new admin audit endpoints.

**Checkpoint**: All AI modules log to audit trail. Human overrides logged with before/after. Admin can view, filter, and export audit log.

---

## Phase 6: User Story 4 — Landing Page Polish (Priority: P4)

**Goal**: Landing page looks professional and trustworthy for beta prospects.

**Independent Test**: Share URL on LinkedIn → branded preview card shows. View on mobile (375px) → no overflow. Visit `/nonexistent` → 404 page.

### Implementation

- [x] T038 [P] [US4] Add Open Graph meta tags to root layout at `frontend/src/app/layout.tsx`
  - Add `openGraph` to the existing `Metadata` export (~line 22-51): title, description, type ("website"), url, siteName, locale ("en_AU"), images (reference a static share image). Add `twitter` card metadata.
- [x] T039 [P] [US4] Create social share image `frontend/public/og-image.png` at `frontend/public/og-image.png`
  - Add a branded OG image (1200x630px recommended). If no design asset exists, create a placeholder with Clairo logo and tagline.
- [x] T040 [P] [US4] Generate favicon and apple-touch-icon from logo at `frontend/public/`
  - Confirm `favicon.ico` (16x16, 32x32), `apple-touch-icon.png` (180x180) exist. Add any missing sizes. Update `frontend/src/app/layout.tsx` `icons` metadata if needed.
- [x] T041 [US4] Update landing page footer at `frontend/src/app/page.tsx`
  - Add ABN to the footer (~line 888-932). Add support/contact email. Ensure legal page links point to correct routes (`/terms`, `/privacy`, `/acceptable-use`). Add "Acceptable Use" link alongside existing "Terms" and "Privacy" links.
- [x] T042 [US4] Add security/trust statement to landing page at `frontend/src/app/page.tsx`
  - Add a section or badge near the existing "ATO Compliant" / "Australian Hosted" badges stating: "Your data is encrypted at rest and in transit. Hosted in Australian data centres."
- [x] T043 [US4] Update pricing section to $299/month introductory price at `frontend/src/app/page.tsx`
  - Ensure the pricing section has either real pricing tiers or a clear "Contact us for pricing" CTA with a link to the contact email or a booking page.
- [ ] T044 [US4] Mobile responsive audit (owner will eyeball) and fixes at `frontend/src/app/page.tsx`
  - Test at 375px viewport width. Fix any horizontal overflow, broken layouts, untappable CTAs. Check all sections: hero, problem, platform, how-it-works, pricing, footer.

**Checkpoint**: OG tags work (test with a link preview tool). Mobile layout clean. Footer has ABN and contact info.

---

## Phase 7: User Story 5 — Cookie Consent (Priority: P5)

**Goal**: Analytics only fire after visitor consents. Banner appears on first visit.

**Independent Test**: Incognito → banner appears, no PostHog in network tab. Accept → PostHog fires, banner gone. Decline → no PostHog, banner gone. Reload → preference remembered.

### Implementation

- [x] T045 [P] [US5] Create cookie consent hook at `frontend/src/hooks/useCookieConsent.ts`
  - Read/write `clairo_cookie_consent` from localStorage. Return `{consent: 'accepted' | 'declined' | null, accept(), decline()}`. Store as JSON: `{status, timestamp, version}`.
- [x] T046 [P] [US5] Create CookieConsentBanner component at `frontend/src/components/CookieConsentBanner.tsx`
  - Fixed to bottom of screen. Text: "We use cookies to improve your experience and analyze site usage." Accept and Decline buttons. Link to cookie policy (`/terms` or a dedicated `/cookies` section). Use shadcn/ui `Card` or custom banner styling. Animates away on choice.
- [x] T047 [US5] Modify analytics provider to gate on consent in `frontend/src/lib/analytics.tsx`
  - Import `useCookieConsent`. Only render PostHog `<script>` and Vercel Speed Insights when consent is `'accepted'`. Keep Sentry unconditional (legitimate interest for error tracking). When consent changes from null to accepted, dynamically load scripts.
- [x] T048 [US5] Add CookieConsentBanner to root layout at `frontend/src/app/layout.tsx`
  - Render `<CookieConsentBanner />` in the root layout body so it appears on all pages (landing, auth, app). Only renders when consent is null.

**Checkpoint**: Cookie consent works end-to-end. PostHog gated. Sentry still loads. Banner remembers preference.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup

- [ ] T049 Run backend linting and type checking: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] T050 Run backend tests: `cd backend && uv run pytest`
- [ ] T051 Run frontend linting and type checking: `cd frontend && npm run lint && npx tsc --noEmit`
- [ ] T052 Verify audit log immutability: confirm PostgreSQL rules still block UPDATE/DELETE on `audit_logs` table
- [ ] T053 Run quickstart.md validation: follow the test scenarios in `specs/052-beta-legal-compliance/quickstart.md` end-to-end

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass: `cd backend && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`
- [ ] TFINAL-2 Push feature branch and create PR
  - Run: `git push -u origin 052-beta-legal-compliance`
  - Run: `gh pr create --title "Spec 052: Beta Legal & Compliance" --body "..."`
- [ ] TFINAL-3 Address review feedback (if any)
- [ ] TFINAL-4 Merge PR to main (squash merge)
- [ ] TFINAL-5 Update ROADMAP.md — mark spec 052 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: Done — already on branch
- **Phase 1 (Setup)**: Shared constants + migration — blocks all user stories
- **Phase 2 (Foundational)**: Backend ToS API — blocks US1 frontend work
- **Phase 3 (US1)**: Legal pages + ToS gate — can start after Phase 2
- **Phase 4 (US2)**: AI disclaimers — can start after Phase 1 (needs constants only)
- **Phase 5 (US3)**: Audit trail — can start after Phase 1 (needs constants only)
- **Phase 6 (US4)**: Landing page — can start after Phase 1
- **Phase 7 (US5)**: Cookie consent — can start after Phase 1
- **Phase 8 (Polish)**: After all user stories complete

### User Story Dependencies

- **US1 (Legal Pages & ToS)**: Depends on Phase 2 (backend API). No dependency on other stories.
- **US2 (AI Disclaimers)**: Depends on Phase 1 (constants). Independent of US1.
- **US3 (Audit Trail)**: Depends on Phase 1 (constants). Independent of US1, US2.
- **US4 (Landing Page)**: Depends on Phase 1. Shares footer work with US1 (T015) — coordinate.
- **US5 (Cookie Consent)**: Depends on Phase 1. Fully independent.

### Within Each User Story

- Models/schemas before services
- Services before endpoints/routes
- Backend before frontend (where frontend depends on API)
- Components before page integration

### Parallel Opportunities

- **Phase 1**: T001 and T002 can run in parallel (backend vs frontend constants)
- **Phase 3 (US1)**: T009, T010, T011, T012, T013 can all run in parallel (separate files)
- **Phase 4 (US2)**: T017 and T019 can run in parallel (separate files)
- **Phase 5 (US3)**: T025 and T026 can run in parallel; T033 parallel with audit event tasks
- **Phase 6 (US4)**: T038, T039, T040 can all run in parallel
- **Phase 7 (US5)**: T045 and T046 can run in parallel
- **Cross-story**: US2, US3, US4, US5 can all run in parallel after Phase 1 (they only need shared constants, not ToS API)

---

## Parallel Example: US1

```
# Parallel batch 1 — all independent pages:
T009: Build accept-terms page
T010: Create legal page layout
T011: Build terms page
T012: Build privacy page
T013: Build acceptable-use page
T016: Build 404 page

# Sequential after batch 1:
T014: Add ToS check to protected layout bootstrap
T015: Update footer links across all layouts
```

## Parallel Example: US3

```
# Parallel batch 1 — audit event definitions:
T025: Create tax planning audit_events.py
T026: Create BAS audit_events.py
T033: Create admin audit schemas

# Sequential — add AuditService calls (each depends on its module):
T027: Tax planning chat audit
T028: Multi-agent orchestrator audit
T029: BAS classification audit
T030: Insights AI analyzer audit
T031: Insights summarizer audit
T032: Human override audit

# Sequential — admin viewer (depends on backend endpoints):
T034: Admin audit router
T035: Admin audit log viewer page
T036: Add audit nav entry
T037: API client functions
```

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete Phase 1: Setup (constants + migration)
2. Complete Phase 2: Foundational (backend ToS API)
3. Complete Phase 3: US1 (legal pages + ToS gate)
4. **STOP AND VALIDATE**: New signup blocked without ToS acceptance. Legal pages render.
5. This alone makes the app legally operable for beta.

### Incremental Delivery

1. Phase 1 + 2 + 3 → **US1 done** — legally operable (MVP)
2. Phase 4 → **US2 done** — disclaimers consistent
3. Phase 5 → **US3 done** — audit trail complete
4. Phase 6 → **US4 done** — landing page polished
5. Phase 7 → **US5 done** — cookie consent live
6. Phase 8 → Polish and ship

### Recommended Parallel Strategy

After Phase 1+2, launch US1 first (legal blocker), then run US2 + US3 + US5 in parallel (all independent), then US4 last (least critical).
