# Feature Specification: Onboarding & Core Hardening

**Feature Branch**: `054-onboarding-hardening`
**Created**: 2026-04-05
**Status**: Draft
**Input**: Harden the onboarding experience, verify all core flows work end-to-end, improve empty states, and close multi-tenancy isolation gaps — all required before beta launch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — First-Run Experience & Empty States (Priority: P1)

A new accountant signs up, completes the onboarding wizard (which already exists), and arrives at the dashboard. The dashboard, client list, BAS workspace, tax planning, and other key screens all show helpful empty states with clear guidance on what to do next — not blank pages.

The onboarding wizard already works (5 steps: create account, select plan, connect Xero, import clients, get started), and a product tour runs on first dashboard visit. This story focuses on ensuring every screen a new user can reach has a useful empty state rather than a blank or confusing view.

The client portal invite flow already works (accountant enters email, magic link sent via Resend, client lands in portal). This story verifies it end-to-end and addresses any portal endpoint TODOs.

**Why this priority**: A new beta customer's first 10 minutes determine whether they stay. Blank screens without guidance cause immediate drop-off.

**Independent Test**: Sign up as a new user with no Xero connection. Navigate to every major screen (dashboard, clients, BAS, tax planning, insights, assistant, portal invites). Every screen shows a meaningful empty state with a CTA to the next action.

**Acceptance Scenarios**:

1. **Given** a new user with no Xero connection, **When** they reach the dashboard, **Then** they see a "Connect Xero to get started" empty state with a direct link to the integrations page.
2. **Given** a user with a Xero connection but no imported clients, **When** they view the clients page, **Then** they see a "Import your first client" empty state with a link to the import flow.
3. **Given** a user viewing a client with no BAS sessions, **When** they open the BAS tab, **Then** they see a "Start your first BAS" empty state with a CTA button.
4. **Given** a user viewing a client with no tax plans, **When** they open the tax planning tab, **Then** they see a "Create your first tax plan" empty state with a CTA.
5. **Given** a user with no insights generated, **When** they view the insights page, **Then** they see a "Generate insights" empty state explaining what insights do.
6. **Given** an accountant invites a client to the portal, **When** the client clicks the magic link, **Then** they can log in and see their dashboard within 3 minutes of receiving the email.
7. **Given** a client in the portal with no shared tax plan, **When** they navigate to the tax plan page, **Then** they see a "Your accountant hasn't shared a tax plan yet" message — not a 404 or error.

---

### User Story 2 — BAS End-to-End Verification (Priority: P2)

The complete BAS workflow is verified to work from start to finish: Xero sync pulls transactions, the transaction review screen loads and allows classification, AI-assisted GST classification works and shows confidence, BAS preparation aggregates correctly, the review and approval flow works, and the export generates valid output.

This story produces integration tests that exercise the full flow. The BAS module is functionally complete on both backend and frontend but currently has no integration test coverage beyond a basic worksheet auth check.

**Why this priority**: BAS is the core product. If the BAS flow breaks, nothing else matters.

**Independent Test**: Run the BAS integration test suite. All tests pass. Manually walk through: create a BAS session for a connected client, review transactions, approve AI suggestions, run GST calculation, approve the session, export as PDF and CSV.

**Acceptance Scenarios**:

1. **Given** a connected Xero client with synced transactions, **When** a BAS session is created, **Then** the session loads with transactions ready for review.
2. **Given** transactions in a BAS session, **When** AI tax code suggestions are generated, **Then** each suggestion shows a confidence score and the suggestion source.
3. **Given** an accountant approves a tax code suggestion, **When** the approval is saved, **Then** the transaction reflects the approved tax code and an audit event is recorded.
4. **Given** all transactions are resolved, **When** the GST calculation runs, **Then** the BAS figures (1A, 1B, G1-G20) are correct and match the underlying transaction data.
5. **Given** a calculated BAS session, **When** the accountant approves it, **Then** the session status changes to "approved" and the figures are locked.
6. **Given** an approved BAS session, **When** the accountant exports it, **Then** a valid PDF working paper and ATO-compliant CSV are generated.
7. **Given** a BAS integration test suite, **When** all tests run, **Then** they all pass and cover: session creation, tax code suggestion, approval, calculation, approval, and export.

---

### User Story 3 — Tax Planning End-to-End Verification (Priority: P3)

The tax planning workflow is verified: create a plan for an individual, company, or trust entity; AI generates scenarios; the accountant reviews and modifies scenarios; a PDF export is generated with correct figures and the AI disclaimer.

**Why this priority**: Tax planning is the second core product and the revenue differentiator.

**Independent Test**: Create tax plans for each entity type (individual, company, trust). Verify AI scenarios generate, figures calculate correctly, and PDF exports include the disclaimer.

**Acceptance Scenarios**:

1. **Given** a connected client, **When** the accountant creates a tax plan, **Then** the plan loads with financial data from Xero.
2. **Given** a tax plan with financial data, **When** the accountant sends a chat message, **Then** the AI responds with relevant scenarios and the response streams within 2 seconds to first token.
3. **Given** a tax plan with scenarios, **When** the accountant runs the multi-agent analysis, **Then** it completes with strategies evaluated, recommended scenarios, accountant brief, and client summary.
4. **Given** a completed tax plan analysis, **When** the accountant exports as PDF, **Then** the PDF includes correct figures, the practice name, and the standardised AI disclaimer.
5. **Given** a tax plan for a company entity, **When** the company tax rate is applied, **Then** the rate matches the current ATO company tax rate for the financial year.
6. **Given** a tax plan for a trust entity, **When** distribution scenarios are generated, **Then** they correctly model different distribution strategies.

---

### User Story 4 — Multi-Tenancy & Data Isolation (Priority: P4)

No tenant can see another tenant's data. No portal user can see another client's data. This is verified at the database level (RLS policies) and the application level (integration tests).

Currently, tables created before February 2026 have RLS policies, but 13+ tables created after that date (tax code suggestions, tax plans, tax scenarios, feedback, classifications, tax plan analyses) only rely on application-level tenant filtering. This story adds the missing RLS policies and writes comprehensive isolation tests.

**Why this priority**: Data isolation is a legal and trust requirement. A single cross-tenant data leak would be catastrophic for an accounting platform.

**Independent Test**: Run the tenant isolation test suite. Every test passes. Verify: tenant A's API calls never return tenant B's data. Portal user only sees their own business. Direct database queries with wrong tenant context return empty results.

**Acceptance Scenarios**:

1. **Given** two tenants (A and B) each with clients, **When** tenant A queries the clients API, **Then** only tenant A's clients are returned — zero results from tenant B.
2. **Given** two tenants with BAS sessions, **When** tenant A queries BAS data, **Then** only tenant A's sessions, calculations, and suggestions are returned.
3. **Given** two tenants with tax plans, **When** tenant A queries tax plans, **Then** only tenant A's plans, scenarios, and analyses are returned.
4. **Given** a portal user for client X, **When** they access the portal API, **Then** they only see data for client X — no other clients' data is accessible.
5. **Given** all tenant-scoped tables, **When** a database query is executed without tenant context set, **Then** RLS policies return empty results (not all rows).
6. **Given** the RLS policy audit, **When** all tenant-scoped tables are checked, **Then** every table with a `tenant_id` column has an active RLS policy.
7. **Given** the repository layer, **When** all repository methods that query tenant-scoped data are audited, **Then** every query includes a `tenant_id` filter.

---

### User Story 5 — Knowledge/RAG Verification (Priority: P5)

Tax compliance queries through the knowledge assistant return relevant, cited results. Citations reference real ATO documents that exist in the knowledge base. No hallucinated citations appear.

**Why this priority**: Incorrect or fabricated tax compliance citations could expose the practice to regulatory risk.

**Independent Test**: Ask 5 tax compliance questions through the knowledge assistant. Each response includes at least one citation. Each cited source exists in the knowledge base and links to a real ATO document.

**Acceptance Scenarios**:

1. **Given** a user asks a GST question through the assistant, **When** the response is returned, **Then** it includes at least one citation with a source reference.
2. **Given** a citation in an assistant response, **When** the citation source is checked, **Then** it corresponds to a real document in the knowledge base (not a hallucinated reference).
3. **Given** the knowledge base has been populated with ATO compliance documents, **When** a compliance query is made, **Then** the response uses information from the ingested documents, not just the LLM's training data.
4. **Given** a query about an obscure tax topic not in the knowledge base, **When** the response is returned, **Then** it clearly indicates limited information is available rather than fabricating an answer.

---

### Edge Cases

- What happens when the Xero OAuth token expires during a BAS session? The system should detect the expired token, prompt the user to re-authenticate, and resume the session without data loss.
- What happens when two accountants in the same practice edit the same BAS session? The second save should fail with a concurrency error rather than silently overwriting.
- What happens when a tenant's subscription is in a trial but the trial expires during a BAS session? The session should complete — do not block mid-workflow. Restrict new session creation instead.
- What happens when a portal invitation link is clicked after expiry (24 hours)? The user sees an "Invitation expired" message with instructions to contact their accountant.
- What happens when RLS is enabled on a table that has existing data without tenant_id? The migration must ensure all rows have a valid tenant_id before enabling RLS, or the rows become invisible.

## Requirements *(mandatory)*

### Functional Requirements

**Onboarding & Empty States**

- **FR-001**: Every major screen accessible to a new user (dashboard, clients, BAS, tax planning, insights, assistant) MUST display a meaningful empty state with a call-to-action when no data exists.
- **FR-002**: Empty states MUST guide the user to the next logical action (e.g., "Connect Xero" → "Import clients" → "Start BAS").
- **FR-003**: The client portal invite flow MUST work end-to-end: accountant enters email → client receives magic link → client accesses portal within 3 minutes.
- **FR-004**: Portal pages with no shared data (e.g., no tax plan shared yet) MUST show a friendly message — not a 404 or error.

**BAS Flow Verification**

- **FR-005**: The BAS workflow MUST complete end-to-end: session creation → transaction review → AI classification → GST calculation → approval → export.
- **FR-006**: AI tax code suggestions MUST display confidence scores and suggestion source.
- **FR-007**: BAS exports MUST produce valid PDF working papers and ATO-compliant CSV files.
- **FR-008**: Integration tests MUST cover the complete BAS workflow including session lifecycle, calculation accuracy, and export generation.

**Tax Planning Verification**

- **FR-009**: Tax planning MUST work for all supported entity types (individual, company, trust).
- **FR-010**: AI scenario generation MUST produce responses within 2 seconds to first token.
- **FR-011**: Tax plan PDF exports MUST include correct figures, practice branding, and the AI disclaimer.
- **FR-012**: Integration tests MUST cover tax plan creation, AI chat, multi-agent analysis, and PDF export.

**Multi-Tenancy & Data Isolation**

- **FR-013**: ALL tables with a `tenant_id` column MUST have active Row-Level Security policies.
- **FR-014**: RLS policies MUST return empty results (not all rows) when no tenant context is set.
- **FR-015**: Integration tests MUST prove that tenant A's API calls never return tenant B's data across all major endpoints (clients, BAS, tax plans, insights, portal).
- **FR-016**: Integration tests MUST prove that a portal user can only access their own business's data.
- **FR-017**: All repository methods querying tenant-scoped data MUST include a `tenant_id` filter.

**Knowledge/RAG Verification**

- **FR-018**: Knowledge assistant responses to compliance queries MUST include at least one citation.
- **FR-019**: All citations MUST reference documents that exist in the knowledge base.
- **FR-020**: When insufficient knowledge base content exists for a query, the response MUST indicate limited information rather than fabricating an answer.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: Portal magic link flow generates auth events (already implemented).
- [ ] **Data Access Events**: No new sensitive data access patterns.
- [x] **Data Modification Events**: RLS policy additions modify database security configuration.
- [ ] **Integration Events**: BAS flow tests exercise Xero integration paths.
- [ ] **Compliance Events**: BAS calculation accuracy directly affects compliance.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|---|---|---|---|---|
| No new audit events | This spec verifies existing audit coverage | N/A | N/A | N/A |

### Compliance Considerations

- **ATO Requirements**: BAS calculation accuracy tests ensure GST figures match transaction data — critical for ATO lodgement compliance.
- **Data Retention**: No changes to retention policies.
- **Access Logging**: Multi-tenancy tests verify that audit log queries are also tenant-scoped.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of major screens show meaningful empty states when no data exists (dashboard, clients, BAS, tax planning, insights, assistant, portal).
- **SC-002**: A new user can go from signup to first BAS session in under 10 minutes (including Xero connection and client import).
- **SC-003**: The BAS integration test suite passes with 100% coverage of the session lifecycle (create → classify → calculate → approve → export).
- **SC-004**: The tax planning integration test suite passes for all entity types (individual, company, trust).
- **SC-005**: 100% of tenant-scoped tables have active RLS policies (zero tables with `tenant_id` but no RLS).
- **SC-006**: The tenant isolation test suite passes — zero cross-tenant data leakage across all tested endpoints.
- **SC-007**: Knowledge assistant responses include verifiable citations for 90%+ of compliance queries.
- **SC-008**: The portal invite-to-login flow completes in under 3 minutes.
- **SC-009**: A portal user cannot access any data belonging to a different client (verified by integration test).

## Assumptions

- Xero sandbox/test credentials are available for integration testing. If not, BAS flow tests will use mocked Xero data.
- The existing product tour (react-joyride, 6 steps) is sufficient as a first-run guided experience. A dedicated BAS-specific walkthrough is deferred to a future spec.
- RLS policies for newer tables will follow the same pattern as existing tables (using the `app.current_tenant_id` session variable).
- The knowledge base has been populated with at least some ATO compliance documents for RAG verification testing.
- Integration tests will use the existing factory pattern (auth.py, portal.py, xero.py factories) for test data creation.
- The tier selection step in onboarding shows $299/month introductory pricing (aligned with spec 052 pricing update). No Stripe integration yet — that's spec 053.
