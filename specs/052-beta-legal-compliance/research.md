# Research: Beta Legal & Compliance

**Branch**: `052-beta-legal-compliance` | **Date**: 2026-04-05

## R1: ToS Acceptance Gate — Where and How

**Decision**: Add `tos_accepted_at` column to the `User` model. Check it in the protected layout's `bootstrap()` call. Redirect to `/accept-terms` when null.

**Rationale**: The protected layout at `frontend/src/app/(protected)/layout.tsx:231-277` already runs a `bootstrap()` check on mount that calls `GET /api/v1/auth/bootstrap`. If the response includes `tos_accepted_at: null`, the layout can redirect to a ToS acceptance page — identical to how it redirects to `/onboarding` when the user has no backend account (line 265). This gates both new and existing users with a single check.

For new users, the onboarding flow already redirects from Clerk signup to `/onboarding` (via `forceRedirectUrl` at sign-up/page.tsx:28). The ToS acceptance screen appears as the first step before account creation.

**Why `User` model (not `PracticeUser` or `Tenant`)**: ToS acceptance is personal, not tenant-scoped. A person accepts once regardless of how many practices they belong to. The `User` model at `auth/models.py:415` is the identity table.

**ToS versioning**: Store `tos_version_accepted: str` alongside `tos_accepted_at`. When the version bumps, the bootstrap check sees a mismatch and redirects again.

**Alternatives considered**:
- Clerk `publicMetadata` for ToS flag — rejected: requires Clerk API calls to update, adds external dependency for a simple DB flag
- Middleware-level check — rejected: middleware cannot access the database (noted in middleware.ts:43-44 comment)
- Onboarding-only gate — rejected: would not catch existing users who signed up before the feature

## R2: AI Disclaimer Standardisation

**Decision**: Create a shared `AIDisclaimer` React component and a backend constant. Replace all 4 ad-hoc disclaimer instances with the shared component/constant.

**Rationale**: The codebase has 4 inconsistent disclaimer instances:
1. `TaxPositionCard.tsx:124-126` — inline text, frontend
2. `tax_plan_export.html:155-159` — HTML template, backend PDF
3. `ai-export-utils.ts:28,70-72` — clipboard export, frontend
4. `tax_planning/router.py:756-762` — inline HTML in secondary PDF export, backend

All use different wording. A single source of truth prevents divergence.

**Frontend**: `components/ui/AIDisclaimer.tsx` — renders the standard text in a subtle banner. Used on tax plan pages, BAS review, and portal views.

**Backend**: `core/constants.py` or similar — `AI_DISCLAIMER_TEXT` constant used in PDF templates and any server-rendered content.

**Standard wording**: "This is AI-assisted decision support for registered tax agents. It does not constitute tax advice. Professional judgement should always be applied."

**Screens needing the disclaimer** (currently missing):
- BAS review/preparation screens
- Client portal tax plan and BAS views
- Any future AI output screen

**Alternatives considered**:
- Per-screen custom disclaimers — rejected: inconsistency risk, harder to update
- Disclaimer in the app shell (global banner) — rejected: too intrusive, not all pages show AI content

## R3: Audit Trail Extension to AI Modules

**Decision**: Add `AuditService.log_event()` calls to all AI-generating service methods. Create `audit_events.py` files for tax_planning and bas modules. Build an admin audit log viewer at `/admin/audit/`.

**Rationale**: The `AuditService` at `core/audit.py:353-454` is mature — SHA-256 checksum chain, immutable table (PostgreSQL rules block UPDATE/DELETE), sensitive data masking. It's already used by 8 modules. But no AI module uses it.

**AI modules with unaudited calls**:

| Module | Location | What to log |
|---|---|---|
| Tax planning chat | `tax_planning/service.py:840-854` | Model, input summary, output summary, token usage |
| Tax planning streaming | `tax_planning/service.py:963-1003` | Model, token usage (logged at stream end) |
| Multi-agent orchestrator | `tax_planning/agents/orchestrator.py:66-170` | Each sub-agent call: model, role, tokens |
| BAS LLM classification | `bas/tax_code_service.py:1079-1084` | Model, transaction context hash, suggested code, confidence |
| BAS client classification | `bas/tax_code_service.py:1201-1203` | Model, classification result |
| Insights AI analyzer | `insights/analyzers/ai_analyzer.py:360-362` | Model, analysis type, token usage |
| Insights summarizer | `insights/service.py:490-492` | Model, summary length, token usage |

**New audit event types** (dot-notation, following existing pattern):
- `ai.tax_planning.chat` — Tax plan conversation turn
- `ai.tax_planning.analysis` — Multi-agent analysis run
- `ai.bas.classification` — LLM tax code suggestion
- `ai.bas.client_classification` — Client-based classification
- `ai.insights.analysis` — AI insight generation
- `ai.suggestion.approved` / `ai.suggestion.modified` / `ai.suggestion.rejected` — Human overrides

**For human override logging**: The tax code resolution module already has an accept/modify/reject flow. Need to add `AuditService.log_event()` at the point where the accountant's decision is persisted, capturing before/after values.

**Admin audit log viewer**: Goes at `frontend/src/app/(protected)/admin/audit/page.tsx`. Backend endpoint at `GET /api/v1/admin/audit` with query params for filtering (date range, event type, user). CSV export via `GET /api/v1/admin/audit/export`.

**Alternatives considered**:
- Use the agents module's `AgentAuditService` (separate tables) — rejected: core `audit_logs` table has immutability guarantees, checksum chain, and is the compliance-grade audit trail
- Log AI calls at the agent/LLM layer (wrapper around Anthropic SDK) — rejected: too low-level, loses business context (which plan, which transaction)

## R4: Cookie Consent Implementation

**Decision**: Build a `CookieConsent` component that gates PostHog and Vercel Speed Insights. Store consent in localStorage. Sentry loads unconditionally (legitimate interest).

**Rationale**: Currently, PostHog loads unconditionally via `frontend/src/lib/analytics.tsx` which is included in the root layout. The `AnalyticsProvider` component (layout.tsx:73) renders script tags immediately.

**Approach**:
1. Create a `useCookieConsent` hook that reads/writes `clairo_cookie_consent` from localStorage
2. Modify `AnalyticsProvider` to check consent before loading PostHog and Speed Insights
3. Render a `CookieConsentBanner` component in the root layout that appears when consent is unset
4. Sentry (`@sentry/nextjs`) is exempt — error tracking is operational, not marketing

**Consent states**: `accepted`, `declined`, or `null` (not yet chosen). If `null`, no non-essential analytics load and the banner shows.

**Alternatives considered**:
- Third-party consent manager (CookieBot, Osano) — rejected: overkill for a simple accept/decline, adds external dependency
- Server-side consent tracking — rejected: consent is per-browser, localStorage is the standard approach
- Cookie-based consent storage — rejected: localStorage is simpler, doesn't need to be sent with requests

## R5: Legal Page Rendering

**Decision**: Build legal pages as static Next.js pages with Markdown content rendered via `@next/mdx` or inline JSX. Content stored as `.mdx` files or string constants.

**Rationale**: Legal pages are rarely-updated static content. They don't need a CMS. MDX allows rich formatting with React components (e.g., table of contents, last-updated date) while keeping the content in the repo for version control.

**Routes**: `/terms`, `/privacy`, `/acceptable-use`. All public (no auth required). Shared layout with Clairo branding, back-to-home link, and footer.

**Content**: Placeholder text initially, clearly marked as "Draft — final version coming soon." Legal drafting is a separate non-code task.

**Alternatives considered**:
- CMS (Contentful, Sanity) — rejected: overkill for 3 static pages
- HTML files served statically — rejected: loses Next.js layout/theming
- Database-stored content — rejected: adds unnecessary complexity for rarely-updated content
