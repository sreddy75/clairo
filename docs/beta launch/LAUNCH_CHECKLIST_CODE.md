# Clairo — Launch Readiness: Code & Platform Implementation

> Items to implement via Claude Code / speckit workflow.
> Grouped into 4 specs, executed in dependency order.

---

## Spec Breakdown

| Spec | ID | Sections | Status |
|------|----|----------|--------|
| **Beta Legal & Compliance** | 052 | 1, 2, 9 | Not started |
| **Stripe Billing** | 053 | 6 | Not started |
| **Onboarding & Core Hardening** | 054 | 3, 4, 5 | Not started |
| **Infra & Launch Polish** | 055 | 7, 8, 10 | Not started |

### Execution Order

1. **052 — Beta Legal & Compliance** (blocks launch)
   - ToS acceptance at signup, AI disclaimers on all outputs, cookie consent
   - Legal pages (terms, privacy, acceptable use, cookies) + landing page polish
   - Audit trail completeness: all AI suggestions logged, immutable append-only log
   - *Why first*: Cannot onboard paying customers without legal compliance

2. **053 — Stripe Billing** | **054 — Onboarding & Core Hardening** (parallel)
   - **053**: Stripe products/prices, signup → subscription, webhooks, dunning, free trial for beta
   - **054**: Onboarding wizard (Xero connect → import → guided BAS), empty states, smoke tests for BAS/tax planning/portal/RAG, multi-tenancy isolation tests
   - *Why parallel*: Independent concerns — billing vs product experience

3. **055 — Infra & Launch Polish** (last)
   - Production deployment pipeline, backups, CORS, Sentry, uptime monitoring
   - Security hardening: rate limiting, dependency audit, OWASP review, MFA
   - Performance: indexes, retry logic, load testing
   - Support: feedback button, FAQ, status page
   - Analytics: product events, landing page tracking
   - *Why last*: Can be incremental, some items are ongoing post-launch

---

## 1. In-App Legal & Consent `→ Spec 052`

### ToS & Privacy Acceptance at Signup
- [ ] Add ToS acceptance checkbox to Clerk signup flow (or post-signup onboarding step)
- [ ] Store `tos_accepted_at` timestamp on the tenant/user record
- [ ] Link to Terms of Service and Privacy Policy in the signup UI
- [ ] Block access until ToS is accepted (middleware or guard)

### AI Disclaimers
- [ ] Add persistent disclaimer banner/footer on all tax planning output screens: *"This is AI-assisted decision support for registered tax agents. It does not constitute tax advice."*
- [ ] Add disclaimer on BAS review/preparation outputs
- [ ] Add disclaimer on any AI-generated PDF exports (tax plans, BAS summaries)
- [ ] Ensure disclaimers are present in the client portal view as well

### Cookie Consent
- [ ] Add cookie consent banner to the app (if using analytics/tracking)
- [ ] Add cookie consent banner to the landing page (if using analytics/tracking)
- [ ] Respect consent preference — don't fire tracking scripts until accepted

---

## 2. Landing Page Updates `→ Spec 052`

### Legal Pages
- [ ] Build Terms of Service page (route: `/terms`)
- [ ] Build Privacy Policy page (route: `/privacy`)
- [ ] Build Acceptable Use Policy page (route: `/acceptable-use`)
- [ ] Build Cookie Policy page (route: `/cookies`) — if applicable
- [ ] Add footer links to all legal pages across every page on the landing site

### Website Polish
- [ ] Add ABN to footer
- [ ] Add support/contact email to footer or contact page
- [ ] Pricing section or "Contact us for pricing" placeholder
- [ ] "Book a demo" or "Get started" CTA for beta customers
- [ ] Open Graph meta tags + social share image for link previews
- [ ] Favicon check (all sizes)
- [ ] 404 page
- [ ] Mobile responsive audit and fixes
- [ ] Security/trust statement (e.g., "Your data is encrypted at rest and in transit")
- [ ] "How it works" section covering BAS workflow + tax planning

---

## 3. Onboarding & First-Run Experience `→ Spec 054`

- [ ] New tenant signup → Clerk auth → tenant record created → redirect to onboarding
- [ ] Onboarding wizard: connect Xero, import first client, guided BAS walkthrough
- [ ] Client portal invite flow: accountant enters client email → magic link sent via Resend → client lands in portal
- [ ] Empty states: helpful messaging when no clients/BAS/plans exist yet ("Connect Xero to get started")

---

## 4. Core Flow Hardening (Smoke Test Targets) `→ Spec 054`

### BAS End-to-End
- [ ] Xero sync pulls transactions correctly
- [ ] Transaction review screen loads and allows classification
- [ ] GST classification (AI-assisted) works and shows confidence
- [ ] BAS preparation screen aggregates correctly
- [ ] Review & approval flow works (accountant sign-off)
- [ ] Export/lodgement-ready output generates correctly

### Tax Planning
- [ ] Individual tax plan: create → AI scenarios generate → review → PDF export
- [ ] Company tax plan: entity-specific rates and deductions apply
- [ ] Trust tax plan: distribution scenarios generate correctly
- [ ] Partnership tax plan: if supported, same flow
- [ ] All PDF exports include AI disclaimers

### Client Portal
- [ ] Business owner can log in via magic link
- [ ] Portal shows BAS status (read-only)
- [ ] Portal shows tax plan (read-only)
- [ ] Portal cannot access other clients' data

### Knowledge / RAG
- [ ] Tax compliance queries return relevant, cited results
- [ ] No hallucinated citations — sources are real and verifiable

---

## 5. Multi-Tenancy & Data Isolation `→ Spec 054`

- [ ] Write integration tests: tenant A's API calls never return tenant B's data
- [ ] Write integration tests: client portal user only sees their own business
- [ ] Audit all repository queries for `tenant_id` filter (automated grep or test)
- [ ] Row-level security policies verified on `tax_plans`, `tax_code_suggestions`, `classification_requests`, `feedback_submissions`, and all other tenant-scoped tables

---

## 6. Billing Integration (Stripe) `→ Spec 053`

- [ ] Stripe product and price objects created for the subscription plan
- [ ] Signup flow creates Stripe customer + subscription
- [ ] Stripe webhook endpoint handles: `invoice.paid`, `invoice.payment_failed`, `customer.subscription.updated`, `customer.subscription.deleted`
- [ ] Subscription status reflected in app (active, past_due, cancelled)
- [ ] Cancellation flow: user can cancel, access continues until period end
- [ ] Alpha/beta: free trial period configured so alpha testers aren't charged
- [ ] Dunning: grace period on failed payment, visual warning in-app, eventual access restriction

---

## 7. Infrastructure & Security `→ Spec 055`

### Production Environment
- [ ] Production deployment pipeline works (separate from staging)
- [ ] Environment variables / secrets isolated per environment
- [ ] Database backups automated (daily + point-in-time recovery)
- [ ] CORS locked to production domain(s) only

### Monitoring
- [ ] Sentry (or equivalent) error tracking integrated — backend + frontend
- [ ] Uptime monitoring on production URL
- [ ] Celery task failure alerting
- [ ] API response time monitoring / slow query logging

### Security Hardening
- [ ] All API endpoints require authentication (audit for any unauthenticated routes)
- [ ] Rate limiting on login, signup, and public-facing endpoints
- [ ] `pip audit` and `npm audit` — resolve critical/high vulnerabilities
- [ ] OWASP top 10 review: SQLi, XSS, CSRF protections in place
- [ ] Clerk MFA setting: enabled or encouraged for accountant users

### Performance
- [ ] Database indexes on all `tenant_id` foreign keys and common query filters
- [ ] Xero API 429 retry logic with exponential backoff
- [ ] Load test with realistic volume (10 practices × 50 clients)
- [ ] Celery: large BAS batch job completes within acceptable time

---

## 8. Support Features (In-App) `→ Spec 055`

- [ ] "Report a bug" or feedback button in the app (links to support email or captures in-app)
- [ ] In-app help / FAQ section (even minimal: "How do I connect Xero?", "What does AI tax planning do?")
- [ ] Status page integration or link (e.g., Instatus, BetterUptime status page)

---

## 9. Audit Trail Completeness `→ Spec 052`

- [ ] All AI suggestions logged with: input, output, model version, timestamp
- [ ] All accountant approvals / overrides logged with: user, timestamp, before/after
- [ ] Audit log is immutable (append-only, no deletes)
- [ ] Audit log accessible to tenant admin (or at minimum, exportable on request)

---

## 10. Analytics & Tracking `→ Spec 055`

- [ ] Track key product events: signup, Xero connected, first BAS started, BAS completed, tax plan created, tax plan exported
- [ ] Google Analytics or Plausible on landing page (respecting cookie consent)
- [ ] Internal dashboard or query for: active tenants, BAS completions, tax plans created
