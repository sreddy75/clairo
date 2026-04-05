# Research: Onboarding & Core Hardening

**Branch**: `054-onboarding-hardening` | **Date**: 2026-04-05

## R1: RLS Policy Pattern for Missing Tables

**Decision**: Use Pattern B (the standard pattern from migration 006 onward) for all 16 tables missing RLS. Create a single Alembic migration.

**Pattern B SQL**:
```sql
ALTER TABLE <table> ENABLE ROW LEVEL SECURITY;

CREATE POLICY <table>_tenant_isolation ON <table>
    FOR ALL
    USING (tenant_id = current_setting('app.current_tenant_id', true)::uuid)
    WITH CHECK (tenant_id = current_setting('app.current_tenant_id', true)::uuid);
```

**16 tables needing RLS**:
1. `portal_invitations`
2. `portal_sessions`
3. `document_request_templates` (nullable tenant_id — policy still works, NULL rows hidden)
4. `bulk_requests`
5. `document_requests`
6. `portal_documents`
7. `tax_code_suggestions`
8. `tax_code_overrides`
9. `classification_requests`
10. `client_classifications`
11. `feedback_submissions`
12. `tax_plans`
13. `tax_scenarios`
14. `tax_plan_messages`
15. `tax_plan_analyses`
16. `implementation_items`

**Note on `document_request_templates`**: Has nullable `tenant_id` (NULL for system templates). The RLS policy will hide system templates when a tenant context is set. If system templates need to be visible to all tenants, a separate policy allowing `tenant_id IS NULL` is needed.

**Alternatives considered**:
- Pattern A (with NULLIF + FORCE) — rejected: Pattern B is the standard used in 10+ subsequent migrations
- Per-module separate migrations — rejected: one migration for all 16 tables is cleaner

## R2: Integration Test Strategy

**Decision**: Extend the existing RLS test file (`test_rls_policies.py`) with tests for all 16 new tables. Replace the placeholder `test_tenant_isolation.py` with real API-level isolation tests. Add BAS and tax planning workflow integration tests.

**Existing test infrastructure**:
- RLS tests at `tests/integration/test_rls_policies.py` use inline fixtures with `set_tenant_context()`/`clear_tenant_context()` helpers
- Factories in `tests/factories/auth.py` provide `TenantFactory`, `UserFactory`, `PracticeUserFactory`, `create_tenant_with_admin()`
- Portal factories in `tests/factories/portal.py`
- Xero factories in `tests/factories/xero.py`
- All tests marked `@pytest.mark.integration`

**Test file plan**:
- `test_rls_policies.py` — extend with 16 new table RLS tests
- `test_tenant_isolation.py` — replace placeholder with API-level cross-tenant tests
- `test_bas_workflow.py` — extend with full lifecycle test (currently only tests auth)
- `test_tax_planning_workflow.py` — new file for tax plan lifecycle
- `test_portal_flow.py` — verify invite-to-login flow end-to-end

**Alternatives considered**:
- Separate test files per table for RLS — rejected: pattern is to group by concern (RLS), not by table
- Mocking Xero for BAS tests — acceptable for CI, but tests should also run with sandbox credentials when available

## R3: Empty State Improvements

**Decision**: Fix 3 key empty state gaps identified during research. Improve portal dashboard empty state, improve portal tax plan 404, and ensure consistent empty state pattern.

**Gaps found**:
1. **Portal dashboard** (`portal/dashboard/page.tsx`): No empty state when portal user has zero shared data. If `dashboard` object is null and no error, nothing renders.
2. **Portal tax plan** (`portal/router.py:286-293`): Returns 404 with "No tax plan shared yet" — backend returns this as an error, frontend likely shows a generic error page.
3. **Insights page** (`insights/page.tsx`): Pure redirect to `/assistant` — no empty state needed (by design).

**Pattern to follow**: Dashboard empty state at `dashboard/page.tsx:617-628` — Building icon + message + CTA button. Consistent with existing design system.

**Alternatives considered**:
- Illustrated empty states with custom artwork — rejected: placeholder illustrations are worse than clean text + icon + CTA
- Onboarding-style wizard for each section — rejected: over-engineering for beta; simple empty states with CTAs are sufficient

## R4: BAS and Tax Planning Test Approach

**Decision**: Write integration tests that exercise the service layer (not HTTP endpoints) for BAS and tax planning workflows. This avoids the complexity of mocking Clerk auth in HTTP tests while still verifying the business logic.

**BAS test approach**: Create a BAS session with factory data, run tax code suggestions (mock the Anthropic API call), approve suggestions, run GST calculation, approve the session, generate export. Verify calculation accuracy and export format.

**Tax planning test approach**: Create a tax plan with factory data, mock the AI agent response, verify scenario creation, verify PDF export includes disclaimer. Test each entity type (individual, company, trust).

**Alternatives considered**:
- Full HTTP integration tests with Clerk mock — feasible but adds complexity for auth mocking
- E2E browser tests — deferred to a separate spec; too slow for CI
