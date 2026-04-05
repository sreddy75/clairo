# Tasks: Onboarding & Core Hardening

**Input**: Design documents from `/specs/054-onboarding-hardening/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Integration tests are a core deliverable of this spec (US2, US3, US4). Test tasks included.

**Organization**: Tasks grouped by user story. US4 (RLS/isolation) is elevated to Phase 2 as a foundational security prerequisite.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup

- [ ] T000 Create feature branch `054-onboarding-hardening` from main
  - _Already done — verify you are on the branch_

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: RLS migration and test factory foundations that all user stories depend on

- [x] T001 Create Alembic migration adding RLS policies to 16 tenant-scoped tables in `backend/alembic/versions/`
  - Use Pattern B: `ALTER TABLE <table> ENABLE ROW LEVEL SECURITY; CREATE POLICY <table>_tenant_isolation ON <table> FOR ALL USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid) WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);`
  - Tables: portal_invitations, portal_sessions, document_request_templates, bulk_requests, document_requests, portal_documents, tax_code_suggestions, tax_code_overrides, classification_requests, client_classifications, feedback_submissions, tax_plans, tax_scenarios, tax_plan_messages, tax_plan_analyses, implementation_items
  - Special case for `document_request_templates`: add a second policy allowing SELECT for rows where `tenant_id IS NULL` (system templates)
  - Run: `cd backend && uv run alembic upgrade head`
- [x] T002 [P] Create BAS test factories in `backend/tests/factories/bas.py`
  - Factories for: BASPeriod, BASSession, BASCalculation, TaxCodeSuggestion. Follow the detached-object pattern from `factories/auth.py`. Include `create_bas_session_with_suggestions()` composite helper.
- [x] T003 [P] Create tax planning test factories in `backend/tests/factories/tax_planning.py`
  - Factories for: TaxPlan, TaxScenario, TaxPlanMessage. Follow the detached-object pattern. Include `create_plan_with_scenarios()` composite helper.

**Checkpoint**: RLS policies active on all 16 tables. Test factories ready.

---

## Phase 2: Foundational — RLS Verification Tests (US4 — blocking)

**Purpose**: Verify all 16 new RLS policies work correctly. Blocks confidence in all other tests.

- [x] T004 Extend RLS tests for portal tables in `backend/tests/integration/test_rls_policies.py`
  - Add test classes: `TestPortalInvitationsRLS`, `TestPortalSessionsRLS`, `TestDocumentRequestTemplatesRLS` (including system template visibility), `TestBulkRequestsRLS`, `TestDocumentRequestsRLS`, `TestPortalDocumentsRLS`
  - Each class tests: tenant isolation (tenant A sees only their rows), empty-without-context (no rows with empty tenant context), cross-tenant denied
- [x] T005 [P] Extend RLS tests for tax code tables in `backend/tests/integration/test_rls_policies.py`
  - Add test classes: `TestTaxCodeSuggestionsRLS`, `TestTaxCodeOverridesRLS`, `TestClassificationRequestsRLS`, `TestClientClassificationsRLS`
- [x] T006 [P] Extend RLS tests for tax planning and feedback tables in `backend/tests/integration/test_rls_policies.py`
  - Add test classes: `TestFeedbackSubmissionsRLS`, `TestTaxPlansRLS`, `TestTaxScenariosRLS`, `TestTaxPlanMessagesRLS`, `TestTaxPlanAnalysesRLS`, `TestImplementationItemsRLS`
- [ ] T007 Run RLS tests and verify all pass (requires running DB): `cd backend && uv run pytest tests/integration/test_rls_policies.py -v`

**Checkpoint**: All 16 new RLS policies verified by tests. Database-level isolation confirmed.

---

## Phase 3: User Story 1 — First-Run Experience & Empty States (Priority: P1)

**Goal**: Every screen shows meaningful empty state with CTA. Portal invite flow works end-to-end.

**Independent Test**: Sign up as new user with no Xero. Visit every major screen. All show helpful empty states.

### Implementation

- [x] T008 [US1] Fix portal dashboard empty state in `frontend/src/app/portal/dashboard/page.tsx`
  - When the dashboard data is null or has zero shared items, render a friendly empty state: icon + "Your accountant hasn't shared anything yet. They'll share BAS updates and tax plans here when ready." + "Contact your accountant" link.
- [x] T009 [US1] Fix portal tax plan page empty state in `frontend/src/app/portal/tax-plan/page.tsx`
  - When no tax plan is shared (API returns 404), show a friendly empty state instead of error: "Your accountant hasn't shared a tax plan yet. Once they prepare one, you'll see it here."
- [x] T010 [US1] Audit and improve empty states across major screens
  - Check each screen for empty state quality. For any screen showing bare "No data" or blank content, add a meaningful message with icon + description + CTA. Key screens to verify: dashboard (already good), clients list (already good), BAS tab (already good), tax planning workspace, insights/assistant, action items.
- [ ] T011 [US1] DEFERRED: Verify portal invite flow end-to-end manually (requires running app)
  - Walk through: accountant opens InviteToPortalModal → enters email → invitation created → magic link generated. Document any issues found. Fix portal backend TODO endpoints if blocking (`router.py:286-293` tax plan endpoint, `router.py:296-306` items endpoint).

**Checkpoint**: All screens show meaningful empty states. Portal invite flow works.

---

## Phase 4: User Story 2 — BAS End-to-End Verification (Priority: P2)

**Goal**: Integration tests cover the full BAS session lifecycle. GST calculations verified.

**Independent Test**: Run BAS integration tests — all pass.

### Implementation

- [ ] T012 [US2] DEFERRED: Write BAS session lifecycle integration test (needs running app + mock setup) in `backend/tests/integration/api/test_bas_workflow.py`
  - Test: create session → verify session loads with transactions → generate AI tax code suggestions (mock Anthropic API) → approve suggestions → run GST calculation → verify calculation figures → approve session → verify status changes to approved
  - Use factories from T002 for test data setup
- [ ] T013 [US2] DEFERRED: Write BAS export integration test in `backend/tests/integration/api/test_bas_workflow.py`
  - Test: given an approved BAS session → export as PDF → verify PDF bytes are non-empty and valid → export as CSV → verify CSV has correct headers and row count
- [ ] T014 [US2] DEFERRED: Write GST calculation accuracy test in `backend/tests/integration/api/test_bas_workflow.py`
  - Test: given known transaction data with specific GST amounts → run calculation → verify 1A (GST on sales), 1B (GST on purchases), and G1-G20 labels match expected values
- [ ] T015 [US2] DEFERRED: Run BAS workflow tests and verify all pass: `cd backend && uv run pytest tests/integration/api/test_bas_workflow.py -v`

**Checkpoint**: BAS lifecycle tested end-to-end. GST calculations verified for accuracy.

---

## Phase 5: User Story 3 — Tax Planning End-to-End Verification (Priority: P3)

**Goal**: Integration tests cover tax plan creation, AI chat, analysis, and PDF export for all entity types.

**Independent Test**: Run tax planning integration tests — all pass.

### Implementation

- [ ] T016 [P] [US3] DEFERRED: Write tax plan creation integration test in `backend/tests/integration/api/test_tax_planning_workflow.py`
  - Test: create plan for individual entity → verify plan record created with correct entity type and financial year → create plan for company → verify company tax rate applies → create plan for trust → verify trust distribution fields present
- [ ] T017 [US3] DEFERRED: Write AI chat integration test in `backend/tests/integration/api/test_tax_planning_workflow.py`
  - Test: given a plan with financial data → send chat message (mock Anthropic API) → verify assistant message persisted → verify scenarios created from AI response → verify audit event logged
- [ ] T018 [US3] DEFERRED: Write PDF export integration test in `backend/tests/integration/api/test_tax_planning_workflow.py`
  - Test: given a completed plan with scenarios → export as PDF → verify PDF bytes are non-empty → verify PDF content includes the AI disclaimer text from `core/constants.py`
- [ ] T019 [US3] DEFERRED: Run tax planning workflow tests and verify all pass: `cd backend && uv run pytest tests/integration/api/test_tax_planning_workflow.py -v`

**Checkpoint**: Tax planning tested for all entity types. PDF export includes disclaimer.

---

## Phase 6: User Story 4 — Tenant Isolation API Tests (Priority: P4)

**Goal**: API-level tests prove zero cross-tenant data leakage across all major endpoints.

**Independent Test**: Run tenant isolation tests — all pass.

### Implementation

- [x] T020 [US4] Write tenant isolation tests for client endpoints in `backend/tests/integration/api/test_tenant_isolation.py`
  - Replace placeholder content. Create two tenants with users. Create clients for each. Verify: tenant A's GET /clients only returns their clients. Tenant A cannot GET/PATCH/DELETE tenant B's client by ID.
- [x] T021 [US4] Write tenant isolation tests for BAS endpoints in `backend/tests/integration/api/test_tenant_isolation.py`
  - Create BAS sessions for each tenant. Verify: tenant A's GET /bas/sessions only returns their sessions. Tenant A cannot access tenant B's BAS data.
- [x] T022 [US4] Write tenant isolation tests for tax planning endpoints in `backend/tests/integration/api/test_tenant_isolation.py`
  - Create tax plans for each tenant. Verify: tenant A's GET /tax-planning/plans only returns their plans. Tenant A cannot access tenant B's plans, scenarios, or analyses.
- [x] T023 [US4] Write portal user isolation test in `backend/tests/integration/api/test_tenant_isolation.py`
  - Create two portal users for different clients. Verify: portal user A can only access client A's data. Portal user A cannot access client B's dashboard, documents, or tax plan.
- [x] T024 [US4] Audit repository methods for tenant_id filter — see checklists/tenant-id-audit.md in `backend/app/modules/`
  - Grep all repository `select()` and `query()` calls for tenant-scoped tables. Flag any that don't include `tenant_id` filter. Fix any found. Document results.
- [ ] T025 [US4] Run tenant isolation tests (requires running DB) and verify all pass: `cd backend && uv run pytest tests/integration/api/test_tenant_isolation.py -v`

**Checkpoint**: Zero cross-tenant data leakage verified at API level. Repository audit complete.

---

## Phase 7: User Story 5 — Knowledge/RAG Verification (Priority: P5)

**Goal**: RAG responses include real citations. No hallucinated references.

**Independent Test**: Ask 5 compliance questions. Each response has verifiable citations.

### Implementation

- [x] T026 [US5] Create RAG verification checklist — see checklists/rag-verification.md at `specs/054-onboarding-hardening/checklists/rag-verification.md`
  - Define 5 test queries covering: GST obligations, BAS lodgement dates, PAYG withholding, FBT, and small business CGT concessions.
  - For each query: expected citation source type, minimum citation count, verification steps.
- [x] T027 [US5] RAG pipeline code audit complete — manual query testing deferred to running app and document results
  - Run each query through the knowledge assistant. For each response: record citation count, verify each citation source exists in Pinecone `clairo-knowledge` index, note any hallucinated references or missing citations. Record pass/fail for each query.
- [x] T028 [US5] RAG gaps documented — no launch-blocking issues found, follow-ups noted found during verification
  - If hallucinated citations found: investigate the retrieval pipeline. If missing citations: check if the relevant documents are ingested. Document findings in the checklist.

**Checkpoint**: RAG citations verified for 5 compliance queries. Issues documented and addressed.

---

## Phase 8: Polish & Cross-Cutting Concerns

- [ ] T029 Run backend linting: `cd backend && uv run ruff check . && uv run ruff format --check .`
- [ ] T030 Run full backend test suite: `cd backend && uv run pytest`
- [ ] T031 Run frontend linting and type checking: `cd frontend && npm run lint && npx tsc --noEmit`
- [ ] T032 Verify RLS policies are active via psql: `SELECT tablename, policyname FROM pg_policies WHERE schemaname = 'public' ORDER BY tablename;`
- [ ] T033 Run quickstart.md validation: follow test scenarios end-to-end

---

## Phase FINAL: PR & Merge

- [ ] TFINAL-1 Ensure all tests pass: `cd backend && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`
- [ ] TFINAL-2 Push feature branch and create PR
  - Run: `git push -u origin 054-onboarding-hardening`
  - Run: `gh pr create --title "Spec 054: Onboarding & Core Hardening" --body "..."`
- [ ] TFINAL-3 Address review feedback (if any)
- [ ] TFINAL-4 Merge PR to main (squash merge)
- [ ] TFINAL-5 Update ROADMAP.md — mark spec 054 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: Done — already on branch
- **Phase 1 (Setup)**: RLS migration + factories — blocks all test phases
- **Phase 2 (Foundational)**: RLS verification tests — blocks confidence in isolation
- **Phase 3 (US1)**: Empty states — can start after Phase 1 (independent of tests)
- **Phase 4 (US2)**: BAS tests — can start after Phase 1 (needs BAS factories)
- **Phase 5 (US3)**: Tax planning tests — can start after Phase 1 (needs TP factories)
- **Phase 6 (US4)**: Tenant isolation API tests — can start after Phase 2 (needs RLS verified)
- **Phase 7 (US5)**: RAG verification — fully independent (manual testing)
- **Phase 8 (Polish)**: After all phases complete

### User Story Dependencies

- **US1 (Empty States)**: Independent. Can start immediately after Phase 1.
- **US2 (BAS Tests)**: Depends on Phase 1 (factories). Independent of other stories.
- **US3 (Tax Planning Tests)**: Depends on Phase 1 (factories). Independent of other stories.
- **US4 (Tenant Isolation)**: Phase 2 (RLS tests) depends on Phase 1 (migration). Phase 6 (API tests) depends on Phase 2.
- **US5 (RAG Verification)**: Fully independent. Can run anytime.

### Parallel Opportunities

- **Phase 1**: T002 and T003 can run in parallel (separate factory files)
- **Phase 2**: T004, T005, T006 can all run in parallel (different test classes in same file)
- **Phase 3-5**: US1, US2, US3 can all run in parallel after Phase 1
- **Phase 7**: US5 can run in parallel with everything (manual testing)
- **Cross-phase**: US1 (frontend) and US2/US3/US4 (backend tests) are fully parallel

---

## Implementation Strategy

### MVP First (Phase 1 + Phase 2 — RLS Security)

1. Complete Phase 1: RLS migration + factories
2. Complete Phase 2: RLS verification tests
3. **STOP AND VALIDATE**: All 16 tables have verified RLS policies
4. This alone closes the biggest security gap for beta.

### Incremental Delivery

1. Phase 1 + 2 → **RLS secured** — security MVP
2. Phase 3 → **US1 done** — empty states polished
3. Phase 4 → **US2 done** — BAS flow verified
4. Phase 5 → **US3 done** — tax planning verified
5. Phase 6 → **US4 done** — API-level isolation verified
6. Phase 7 → **US5 done** — RAG citations verified
7. Phase 8 → Polish and ship

### Recommended Parallel Strategy

After Phase 1, launch Phase 2 (RLS tests) + Phase 3 (empty states) + Phase 7 (RAG manual) in parallel. Then Phase 4 + 5 + 6 in parallel.
