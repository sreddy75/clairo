# Tasks: Stripe Billing — Beta Launch Readiness

**Input**: Design documents from `/specs/043-stripe-billing/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/

**Tests**: Not explicitly requested. Test tasks omitted.

**Organization**: Tasks grouped by user story. No database migrations needed — all models exist.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in all descriptions

---

## Phase 0: Git Setup

- [x] T000 Checkout the feature branch
  - Run: `git checkout 043-stripe-billing` (branch already exists)
  - Verify: You are on the `043-stripe-billing` branch

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Environment configuration needed before any user story work

- [x] T001 Add `STRIPE_WEBHOOK_SECRET` to `backend/.env` with placeholder value
- [x] T002 [P] Add `subscription_status` type to `frontend/src/types/billing.ts` — add `SubscriptionStatus` type union: `"trial" | "active" | "past_due" | "suspended" | "cancelled" | "grandfathered"`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Backend changes that ALL user stories depend on — bootstrap response and subscription guard

**CRITICAL**: No user story work can begin until this phase is complete

- [x] T003 Add `subscription_status` and `can_access` fields to bootstrap response in `backend/app/modules/auth/router.py` — in the `bootstrap` endpoint (~line 314), add `tenant.subscription_status.value` and `tenant.can_access` to the response dict. Update the `BootstrapResponse` schema in `backend/app/modules/auth/schemas.py` to include these 2 fields
- [x] T004 Create `require_active_subscription` FastAPI dependency in `backend/app/modules/billing/middleware.py` — NEW file. Import `get_current_tenant` from `app.core.dependencies`, check `tenant.can_access` property, raise `HTTPException(403)` with code `SUBSCRIPTION_REQUIRED` if False. Include `subscription_status` and `billing_url` in error details
- [x] T005 Consume `subscription_status` and `can_access` in protected layout at `frontend/src/app/(protected)/layout.tsx` — in the bootstrap response handler (~line 254), extract the 2 new fields and store in component state. Pass them down via context or props as needed

**Checkpoint**: Bootstrap returns subscription status, guard dependency exists, frontend has access to status

---

## Phase 3: User Story 1 — Webhook-Driven Subscription Sync (Priority: P1)

**Goal**: Stripe webhook events update tenant subscription status and send email notifications automatically

**Independent Test**: Run `stripe listen --forward-to localhost:8000/api/v1/billing/webhooks/stripe`, then `stripe trigger invoice.payment_failed` — verify tenant status changes to PAST_DUE in database and email is sent

- [ ] T006 [US1] Add audit logging to webhook status change handlers in `backend/app/modules/billing/webhooks.py` — in `_handle_subscription_updated`, `_handle_subscription_deleted`, `_handle_invoice_paid`, and `_handle_invoice_payment_failed`, add `AuditService.log_event()` calls with event_type `billing.subscription.status_changed`, capturing old_status and new_status
- [ ] T007 [US1] Verify webhook signature verification works with real Stripe CLI secret — update `STRIPE_WEBHOOK_SECRET` in `backend/.env` with the signing secret from `stripe listen` output. Test by sending a real event and confirming it processes (not a signature error)
- [ ] T008 [US1] Test all 7 webhook handlers end-to-end with Stripe CLI — run `stripe trigger` for each event type: `customer.subscription.created`, `customer.subscription.updated`, `customer.subscription.deleted`, `customer.subscription.trial_will_end`, `checkout.session.completed`, `invoice.paid`, `invoice.payment_failed`. Verify database state changes and email delivery for each
- [ ] T009 [US1] Test webhook idempotency — send the same Stripe event twice via CLI, verify the second delivery returns success but does not reprocess or send duplicate emails. Check `BillingEvent` table has only one record per `stripe_event_id`

**Checkpoint**: Webhooks process real Stripe events, update tenant status, send emails, handle duplicates

---

## Phase 4: User Story 2 — Access Restriction for Lapsed Subscriptions (Priority: P1)

**Goal**: Suspended/cancelled tenants see restriction UI and cannot perform write operations

**Independent Test**: Manually set a tenant's `subscription_status` to `suspended` in the database, refresh the app — verify restriction banner appears and write operations are blocked

- [x] T010 [US2] Apply `require_active_subscription` dependency to write endpoints — add `Depends(require_active_subscription)` to these routers: Xero sync endpoints in `backend/app/modules/integrations/xero/router.py`, BAS session creation in `backend/app/modules/bas/router.py`, tax plan creation in `backend/app/modules/tax_planning/router.py`, AI query endpoint in `backend/app/modules/knowledge/router.py`, classification request in `backend/app/modules/bas/router.py`
- [x] T011 [P] [US2] Create `SubscriptionBanner` component at `frontend/src/components/billing/SubscriptionBanner.tsx` — persistent, non-dismissible banner for SUSPENDED status. Coral background, text "Your subscription needs attention — update your payment method to continue using Clairo", "Resolve" button linking to `/settings/billing`. For PAST_DUE, show amber background with grace period days remaining
- [x] T012 [P] [US2] Create subscription-expired page at `frontend/src/app/(protected)/subscription-expired/page.tsx` — shown when status is CANCELLED. Card with "Your subscription has ended" heading, options to resubscribe (link to `/settings/billing`) or export data. Use Clairo design system (shadcn Card, warm off-white bg)
- [x] T013 [US2] Add subscription status gating logic to protected layout at `frontend/src/app/(protected)/layout.tsx` — after bootstrap, check `subscription_status`: if CANCELLED redirect to `/subscription-expired`, if SUSPENDED render `SubscriptionBanner` above main content (non-dismissible), if PAST_DUE render `SubscriptionBanner` in warning mode (dismissible). ACTIVE/TRIAL/GRANDFATHERED: no banner

**Checkpoint**: Suspended tenants see banner + blocked writes. Cancelled tenants see expired page. Past-due shows warning.

---

## Phase 5: User Story 3 — Payment Method Collection (Priority: P2)

**Goal**: Trial users can add payment method before trial ends via Stripe Customer Portal

**Independent Test**: With a trial tenant at 3 days remaining, verify the trial banner shows "Add Payment Method" button, clicking it opens Stripe Customer Portal, and returning shows updated billing state

- [x] T014 [US3] Update `TrialBanner` at `frontend/src/components/billing/TrialBanner.tsx` — when `daysRemaining <= 3`, add an "Add Payment Method" button next to the existing "Billing Settings" button. The new button calls `openBillingPortal()` from `@/lib/api/billing`. Use primary variant (coral) for emphasis. Keep the existing subtle banner for >3 days
- [x] T015 [US3] Update `SubscriptionCard` at `frontend/src/components/billing/SubscriptionCard.tsx` — show "Manage Billing" button for trial users (currently hidden by condition `subscription.status !== 'trial'` at ~line 298). Change condition to allow trial users to access portal for payment method entry. Label it "Add Payment Method" for trial, "Manage Billing" for active
- [ ] T016 [US3] Verify `trial_will_end` webhook sends reminder email — trigger `stripe trigger customer.subscription.trial_will_end`, verify the email template renders correctly with practice name, tier, price ($299), and billing date. Check email arrives via Resend

**Checkpoint**: Trial users see "Add Payment Method" CTA when ≤3 days remain, can access Stripe Portal

---

## Phase 6: User Story 4 — Billing Settings Self-Service (Priority: P2)

**Goal**: Billing settings page works end-to-end with real Stripe data

**Independent Test**: Navigate to `/settings/billing`, verify plan shows "$299/month Starter", click "Manage Billing" to open Stripe Customer Portal, return to Clairo and verify page refreshes with correct data

- [x] T017 [US4] Update `SubscriptionCard` to handle SUSPENDED status at `frontend/src/components/billing/SubscriptionCard.tsx` — add `suspended` case to `getStatusColor` function (~line 59). Show red badge "Suspended", message "Your subscription is suspended. Add a payment method to reactivate.", and a prominent "Reactivate" button that calls `openBillingPortal()`
- [ ] T018 [US4] Fix price display in billing UI — verify `$299/month` AUD shows consistently in `SubscriptionCard`, `TrialBanner`, and billing settings page. Check that `TIER_PRICING["starter"]` (29900 cents) converts correctly in all display contexts
- [ ] T019 [US4] Verify billing history page at `frontend/src/app/(protected)/settings/billing/history/page.tsx` — confirm it fetches real `BillingEvent` records from `/api/v1/billing/billing/events` and displays them with correct dates, amounts (formatted as AUD), and event types

**Checkpoint**: Billing page shows accurate data for all 6 statuses, portal integration works

---

## Phase 7: User Story 5 — Dunning / Grace Period (Priority: P3)

**Goal**: Failed payments show grace period warning, access restricted after 7 days

**Independent Test**: Simulate payment failure via `stripe trigger invoice.payment_failed`, verify PAST_DUE banner shows with countdown, wait for subscription pause (or manually set SUSPENDED), verify access restriction activates

- [x] T020 [US5] Create `PaymentFailedBanner` at `frontend/src/components/billing/PaymentFailedBanner.tsx` — amber warning banner: "Payment failed — update your payment method within X days to avoid service interruption". Calculate days remaining from `current_period_end`. Include "Update Payment" button calling `openBillingPortal()`. Non-dismissible
- [x] T021 [US5] Wire `PaymentFailedBanner` into protected layout at `frontend/src/app/(protected)/layout.tsx` — show when `subscription_status === "past_due"`. Pass `current_period_end` from trial_status or a new bootstrap field for grace period calculation
- [ ] T022 [US5] Verify payment recovery flow — trigger `invoice.payment_failed` then `invoice.paid` via Stripe CLI. Confirm: PAST_DUE → banner appears → payment succeeds → ACTIVE → banner disappears. No manual intervention needed

**Checkpoint**: Failed payments show countdown banner, successful retry restores access automatically

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T023 [P] Run frontend type-check — `cd frontend && npx tsc --noEmit`. Fix any type errors from new components
- [ ] T024 [P] Run backend lint — `cd backend && uv run ruff check .`. Fix any lint issues in modified files
- [ ] T025 Run quickstart.md verification checklist — execute each item in `specs/043-stripe-billing/quickstart.md` verification section and confirm all pass
- [ ] T026 Update `HANDOFF.md` — mark Spec 053 (Stripe Billing) as DONE in the launch checklist

---

## Phase FINAL: PR & Merge

- [ ] T027 Run full validation suite
  - Run: `cd backend && uv run ruff check . && uv run pytest`
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`

- [ ] T028 Commit all changes and push
  - Stage modified files, commit with descriptive message
  - Push to remote

- [ ] T029 Update ROADMAP.md
  - Mark Spec 053 (Stripe Billing) as COMPLETE
  - Update current focus to Spec 055 (Infra & Launch Polish)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0** (Git): MUST be first
- **Phase 1** (Setup): After Phase 0 — environment config
- **Phase 2** (Foundational): After Phase 1 — BLOCKS all user stories
- **Phase 3** (US1 Webhooks): After Phase 2
- **Phase 4** (US2 Access Restriction): After Phase 2 — can parallel with US1
- **Phase 5** (US3 Trial Conversion): After Phase 2 — can parallel with US1/US2
- **Phase 6** (US4 Billing Settings): After Phase 2 — can parallel
- **Phase 7** (US5 Dunning): After Phase 4 (needs access restriction components)
- **Phase 8** (Polish): After all user stories

### User Story Dependencies

- **US1** (Webhooks): Independent — only needs foundational phase
- **US2** (Access Restriction): Independent — only needs foundational phase
- **US3** (Trial Conversion): Independent — only needs foundational phase
- **US4** (Billing Settings): Independent — only needs foundational phase
- **US5** (Dunning): Depends on US2 (uses SubscriptionBanner/PaymentFailedBanner patterns)

### Parallel Opportunities

After Phase 2 completes, US1-US4 can all run in parallel:
- US1 (T006-T009): Backend webhook testing
- US2 (T010-T013): Backend guard + frontend banners
- US3 (T014-T016): Frontend trial conversion
- US4 (T017-T019): Frontend billing polish

Within each story, tasks marked [P] can run in parallel.

---

## Implementation Strategy

### MVP First (US1 + US2 Only)

1. Complete Phase 1 + Phase 2 (Setup + Foundational)
2. Complete Phase 3 (US1: Webhooks work)
3. Complete Phase 4 (US2: Access restriction works)
4. **STOP and VALIDATE**: Webhooks sync status, lapsed tenants are restricted
5. This is a shippable MVP — billing enforcement works

### Full Delivery

6. Complete Phase 5 (US3: Trial conversion UX)
7. Complete Phase 6 (US4: Billing settings polish)
8. Complete Phase 7 (US5: Dunning grace period)
9. Phase 8 (Polish) + Phase FINAL (PR)

---

## Notes

- Zero database migrations needed — all models exist
- Backend billing module is 90% built — most tasks are wiring and verification
- Stripe CLI required for webhook testing: `brew install stripe/stripe-cli/stripe`
- 29 tasks total across 9 phases
- MVP scope: 14 tasks (Phase 0-4) for core billing enforcement
