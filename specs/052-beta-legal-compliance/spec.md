# Feature Specification: Beta Legal & Compliance

**Feature Branch**: `052-beta-legal-compliance`
**Created**: 2026-04-05
**Status**: Draft
**Input**: Implement in-app legal consent (ToS, AI disclaimers, cookie consent), landing page legal pages and polish, and audit trail completeness — all required before beta launch.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Legal Pages & Terms Acceptance (Priority: P1)

A new accountant signs up for Clairo. During or immediately after Clerk signup, they are presented with a Terms of Service acceptance step. They must accept the Terms of Service and Privacy Policy before accessing any part of the application. The ToS and Privacy Policy are full legal pages accessible from the footer of every page on the site. An Acceptable Use Policy page is also available.

Existing accountants who signed up before the ToS gate was added are prompted to accept on their next login. Until they accept, they cannot proceed past the acceptance screen.

The footer across the landing page, auth pages, and in-app pages links to all legal pages. The landing page footer already links to `/terms` and `/privacy` but those routes return 404 — this story makes them real.

**Why this priority**: Cannot onboard paying customers without Terms of Service acceptance. Legal pages are the minimum requirement for commercial operation.

**Independent Test**: Sign up as a new user, verify ToS acceptance is required before reaching the dashboard. Visit `/terms`, `/privacy`, and `/acceptable-use` — all render correctly. Verify the acceptance timestamp is recorded.

**Acceptance Scenarios**:

1. **Given** a new user completes Clerk signup, **When** they are redirected to onboarding, **Then** they see a ToS acceptance screen before any other content.
2. **Given** the ToS acceptance screen is shown, **When** the user has not checked the acceptance checkbox, **Then** the "Continue" button is disabled.
3. **Given** the user accepts ToS, **When** they click "Continue," **Then** the acceptance timestamp is recorded and they proceed to onboarding.
4. **Given** an existing user who has not accepted ToS, **When** they log in, **Then** they are redirected to the ToS acceptance screen before accessing the dashboard.
5. **Given** a user who has already accepted ToS, **When** they log in, **Then** they proceed directly to the dashboard without interruption.
6. **Given** any page on the site, **When** a user scrolls to the footer, **Then** they see links to Terms of Service, Privacy Policy, and Acceptable Use Policy.
7. **Given** a visitor navigates to `/terms`, `/privacy`, or `/acceptable-use`, **When** the page loads, **Then** they see the full legal document with appropriate headings, last-updated date, and Clairo branding.

---

### User Story 2 — AI Disclaimers on All Outputs (Priority: P2)

Every screen that displays AI-generated content shows a clear, consistent disclaimer. This includes tax planning outputs, BAS review/preparation screens, AI-generated PDF exports, and the client portal view. The disclaimer communicates that the content is AI-assisted decision support for registered tax agents and does not constitute tax advice.

Currently, disclaimers exist in 4 places with inconsistent wording. This story standardises them into a single reusable pattern with consistent language.

**Why this priority**: Australian tax compliance requires clear communication that AI outputs are not formal tax advice. Inconsistent or missing disclaimers create legal exposure.

**Independent Test**: Navigate to every AI output screen (tax plan view, BAS review, PDF export, client portal), verify the disclaimer is visible and uses the standard wording.

**Acceptance Scenarios**:

1. **Given** a user views a tax plan, **When** the page renders, **Then** a disclaimer is visible stating the content is AI-assisted decision support and does not constitute tax advice.
2. **Given** a user views a BAS review or preparation screen, **When** AI-assisted content is displayed, **Then** the same standard disclaimer is visible.
3. **Given** a user exports a tax plan as PDF, **When** the PDF is generated, **Then** the disclaimer appears in the document footer or a dedicated disclaimer section.
4. **Given** a business owner views their tax plan or BAS status in the client portal, **When** the page renders, **Then** the disclaimer is visible.
5. **Given** any AI disclaimer across the application, **When** compared to the standard wording, **Then** all instances use identical language.
6. **Given** a user copies AI-generated text to clipboard, **When** the text is pasted, **Then** the disclaimer text is included (existing behaviour — verify it uses the standard wording).

---

### User Story 3 — Audit Trail Completeness (Priority: P3)

All AI interactions are logged in the immutable audit trail. When the AI suggests a tax code, generates a tax plan scenario, or produces any recommendation, the system records: what input was provided, what output was generated, which model produced it, and when. When an accountant approves, modifies, or rejects an AI suggestion, the system records: who acted, when, and the before/after state.

Tenant administrators can view a filterable audit log within the application and export it as a CSV for compliance purposes.

The existing `AuditService` and immutable `audit_logs` table provide the infrastructure. This story extends coverage to all AI-generating modules (tax planning, tax code suggestions, BAS classification) and adds the admin-facing viewer.

**Why this priority**: ATO compliance requires a complete audit trail of all decisions affecting tax filings. AI suggestions and human overrides are the most critical events to capture.

**Independent Test**: Generate a tax plan, approve a tax code suggestion, then view the audit log — verify both the AI suggestion event and the approval event appear with full detail. Export the log as CSV and verify the data matches.

**Acceptance Scenarios**:

1. **Given** the AI generates a tax plan scenario, **When** the response completes, **Then** an audit event is recorded with: input parameters, output summary, model identifier, and timestamp.
2. **Given** the AI suggests a tax code for a transaction, **When** the suggestion is presented, **Then** an audit event is recorded with: transaction context, suggested code, confidence score, and model identifier.
3. **Given** an accountant approves an AI suggestion, **When** they confirm, **Then** an audit event is recorded with: the accountant's identity, timestamp, and the approved value.
4. **Given** an accountant modifies an AI suggestion, **When** they save the change, **Then** an audit event is recorded with: the accountant's identity, timestamp, original AI suggestion (before), and the accountant's chosen value (after).
5. **Given** an accountant rejects an AI suggestion, **When** they dismiss it, **Then** an audit event is recorded with: the accountant's identity, timestamp, the rejected suggestion, and the replacement value (if provided).
6. **Given** a tenant administrator navigates to the audit log, **When** the page loads, **Then** they see a filterable, paginated list of audit events for their tenant.
7. **Given** the audit log view, **When** the administrator applies filters (date range, event type, user), **Then** the list updates to show only matching events.
8. **Given** the audit log view, **When** the administrator clicks "Export CSV," **Then** a CSV file downloads containing all events matching the current filters.
9. **Given** the audit log table in the database, **When** any attempt is made to UPDATE or DELETE a record, **Then** the operation is blocked by the database (existing immutability rules — verify they still apply).

---

### User Story 4 — Landing Page Polish (Priority: P4)

The landing page is updated to look professional and trustworthy for beta launch. This includes: ABN displayed in the footer, support/contact email visible, a pricing section (or "Contact us" placeholder), a prominent "Book a Demo" or "Get Started" call-to-action, Open Graph meta tags for social sharing with a branded preview image, correct favicons at all sizes, a custom 404 page, mobile-responsive layout verified and fixed, a security/trust statement, and a clear "How it works" section covering the BAS workflow and tax planning.

**Why this priority**: First impressions for beta prospects. Not a legal blocker but important for credibility and conversion.

**Independent Test**: Share the landing page URL on LinkedIn/Slack — verify the preview card shows correct title, description, and image. View on mobile — verify no layout breaks. Visit a non-existent URL — verify the 404 page renders.

**Acceptance Scenarios**:

1. **Given** the landing page footer, **When** a visitor views it, **Then** it displays the ABN and a support/contact email address.
2. **Given** the landing page, **When** a visitor scrolls to the pricing section, **Then** they see either pricing tiers or a "Contact us for pricing" placeholder with a CTA.
3. **Given** the landing page, **When** a visitor clicks "Book a Demo" or "Get Started," **Then** they are directed to the signup flow or a booking page.
4. **Given** the landing page URL is shared on social media, **When** the platform fetches the link preview, **Then** it shows a branded title, description, and preview image (Open Graph tags).
5. **Given** a browser or device, **When** it requests the favicon, **Then** it receives correctly sized icons (16x16, 32x32, apple-touch-icon, etc.).
6. **Given** a visitor navigates to a non-existent URL, **When** the page loads, **Then** they see a branded 404 page with a link back to the homepage.
7. **Given** the landing page on a mobile device (viewport 375px), **When** the visitor scrolls through all sections, **Then** no content overflows, no horizontal scroll appears, and all CTAs are tappable.
8. **Given** the landing page, **When** a visitor reads the "How it works" section, **Then** it clearly explains the BAS workflow and tax planning process in plain language.
9. **Given** the landing page, **When** a visitor looks for trust signals, **Then** they see a security statement (e.g., "Your data is encrypted at rest and in transit") and the existing "ATO Compliant" / "Australian Hosted" badges.

---

### User Story 5 — Cookie Consent (Priority: P5)

Visitors to the landing page and logged-in users see a cookie consent banner on first visit. The banner explains what cookies and analytics are used and offers Accept / Decline options. Analytics scripts (PostHog, Vercel Speed Insights) only fire after the visitor consents. The consent preference is remembered so the banner does not reappear.

Currently, PostHog and Vercel Speed Insights load unconditionally on every page. This story gates them behind consent.

**Why this priority**: Regulatory best practice (Australian Privacy Act + GDPR for any EU visitors). Lower priority than legal pages and disclaimers because Australian cookie law is less prescriptive than GDPR, but still expected for a professional SaaS product.

**Independent Test**: Visit the landing page in a fresh browser session — verify the cookie banner appears. Decline cookies, reload — verify PostHog does not fire (check network tab). Accept cookies, reload — verify PostHog fires and the banner does not reappear.

**Acceptance Scenarios**:

1. **Given** a first-time visitor to any page, **When** the page loads, **Then** a cookie consent banner appears at the bottom of the screen.
2. **Given** the cookie consent banner, **When** the visitor clicks "Accept," **Then** analytics scripts load, the consent preference is saved, and the banner disappears.
3. **Given** the cookie consent banner, **When** the visitor clicks "Decline," **Then** analytics scripts do NOT load, the consent preference is saved, and the banner disappears.
4. **Given** a visitor who previously accepted cookies, **When** they return to the site, **Then** analytics scripts load automatically and the banner does not appear.
5. **Given** a visitor who previously declined cookies, **When** they return to the site, **Then** analytics scripts do NOT load and the banner does not appear.
6. **Given** the cookie consent banner, **When** displayed, **Then** it includes a link to the Cookie Policy page explaining what is tracked and why.
7. **Given** Sentry error tracking, **When** cookie consent status is "declined," **Then** Sentry still loads (error tracking is a legitimate interest, not marketing analytics) but PostHog and Speed Insights do not.

---

### Edge Cases

- What happens when the ToS content is updated after a user has already accepted? The system tracks the version accepted. If the ToS version changes, users are prompted to re-accept on next login.
- What happens if a user dismisses the cookie banner without making a choice (e.g., navigates away)? The banner reappears on the next page load. No analytics fire until explicit consent.
- What happens if the audit log export is very large (10,000+ events)? The export streams the CSV rather than loading all records into memory. A reasonable limit (e.g., 50,000 rows) with a date range filter prevents runaway exports.
- What happens if a user visits a legal page before it has been populated with final legal text? The page renders with placeholder text clearly marked as "Draft — final version coming soon" rather than a 404.
- What happens when the client portal business owner has not accepted any ToS? Business owners access via magic link and are not subscribers — they do not need to accept subscriber ToS. However, the AI disclaimer must still be visible on their portal views.

## Requirements *(mandatory)*

### Functional Requirements

**Legal Pages & ToS**

- **FR-001**: System MUST present a Terms of Service acceptance step to all new users after signup and before first access to the application.
- **FR-002**: System MUST record the ToS acceptance with: user identifier, timestamp, and ToS version accepted.
- **FR-003**: System MUST block access to all protected routes until the user has accepted the current ToS version.
- **FR-004**: System MUST prompt existing users who have not accepted the current ToS version to accept on their next login.
- **FR-005**: System MUST serve full legal documents at `/terms`, `/privacy`, and `/acceptable-use` routes, accessible without authentication.
- **FR-006**: All pages across the site (landing, auth, in-app) MUST include footer links to the legal pages.

**AI Disclaimers**

- **FR-007**: System MUST display a standardised AI disclaimer on all screens showing AI-generated content, including: tax plan views, BAS review/preparation screens, and the client portal.
- **FR-008**: All AI-generated PDF exports MUST include the standard disclaimer.
- **FR-009**: The disclaimer text MUST communicate: (a) the content is AI-assisted decision support, (b) it is intended for registered tax agents, and (c) it does not constitute tax advice.
- **FR-010**: All disclaimer instances MUST use identical wording sourced from a single definition.

**Cookie Consent**

- **FR-011**: System MUST display a cookie consent banner to all first-time visitors before any non-essential analytics scripts execute.
- **FR-012**: Analytics scripts (product analytics, speed insights) MUST NOT execute until the visitor has given explicit consent.
- **FR-013**: System MUST remember the visitor's consent preference across sessions (minimum 12 months).
- **FR-014**: Error tracking (Sentry) MAY load without explicit consent as a legitimate operational interest, but product analytics MUST NOT.

**Audit Trail**

- **FR-015**: System MUST log all AI-generated suggestions with: input parameters, output content summary, model identifier, and timestamp.
- **FR-016**: System MUST log all accountant actions on AI suggestions (approve, modify, reject) with: actor identity, timestamp, original value, and new value.
- **FR-017**: The audit log MUST be immutable — no UPDATE or DELETE operations permitted on audit records.
- **FR-018**: Tenant administrators MUST be able to view a filterable, paginated audit log within the application.
- **FR-019**: Tenant administrators MUST be able to export the audit log as CSV, filtered by date range and event type.
- **FR-020**: Audit events MUST be retained for a minimum of 7 years for ATO compliance.

**Landing Page**

- **FR-021**: The landing page footer MUST display the company ABN and a support/contact email.
- **FR-022**: The landing page MUST include Open Graph meta tags (title, description, image) for social media link previews.
- **FR-023**: The site MUST serve correct favicons at standard sizes (16x16, 32x32, apple-touch-icon).
- **FR-024**: The site MUST serve a branded 404 page for non-existent routes.
- **FR-025**: The landing page MUST render correctly on mobile viewports (375px minimum width) with no horizontal overflow.
- **FR-026**: The landing page MUST include a security/trust statement communicating data encryption practices.
- **FR-027**: The landing page MUST include a "How it works" section explaining the BAS and tax planning workflows.

### Key Entities

- **ToS Acceptance**: Records a user's agreement to a specific version of the Terms of Service. Linked to the user/tenant. Stores version identifier, acceptance timestamp, and IP address.
- **Audit Event (AI Suggestion)**: Extends the existing audit event model with fields for: AI model identifier, input parameters hash, output content summary, and confidence score.
- **Audit Event (Human Override)**: Extends the existing audit event model with fields for: original AI value, replacement value, and override reason (optional).
- **Cookie Consent Preference**: Client-side record of the visitor's analytics consent choice. Stores consent status (accepted/declined) and timestamp.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [x] **Authentication Events**: ToS acceptance is an authentication-adjacent event that must be logged.
- [ ] **Data Access Events**: No new sensitive data access. Audit log viewer is read-only access to existing audit data.
- [x] **Data Modification Events**: AI suggestions and human overrides create new audit records. ToS acceptance modifies user state.
- [ ] **Integration Events**: No external system integration in this feature.
- [ ] **Compliance Events**: Audit trail completeness directly supports BAS compliance.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|---|---|---|---|---|
| user.tos.accepted | User accepts ToS | User ID, ToS version, timestamp, IP | 7 years | IP address |
| ai.suggestion.generated | AI produces a recommendation | Tenant ID, model ID, input hash, output summary, confidence | 7 years | None (input hashed) |
| ai.suggestion.approved | Accountant approves AI suggestion | Actor ID, suggestion ID, timestamp | 7 years | None |
| ai.suggestion.modified | Accountant modifies AI suggestion | Actor ID, suggestion ID, original value, new value, timestamp | 7 years | May contain financial data |
| ai.suggestion.rejected | Accountant rejects AI suggestion | Actor ID, suggestion ID, rejected value, replacement value, timestamp | 7 years | May contain financial data |

### Compliance Considerations

- **ATO Requirements**: All decisions affecting BAS figures and tax filings must have a complete, tamper-evident audit trail. The existing immutable `audit_logs` table with SHA-256 checksum chain satisfies this.
- **Data Retention**: 7-year minimum for all audit events per ATO requirements.
- **Access Logging**: Tenant administrators can view their own tenant's audit log. Platform administrators can view all. The audit log viewer itself should log access events.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: 100% of new signups encounter the ToS acceptance step before accessing the application.
- **SC-002**: All three legal pages (`/terms`, `/privacy`, `/acceptable-use`) are accessible and render correctly on desktop and mobile.
- **SC-003**: Every screen displaying AI-generated content shows the standard disclaimer — zero screens with missing or inconsistent wording.
- **SC-004**: 100% of AI suggestions across all modules (tax planning, tax code, BAS classification) generate an audit event with input, output, model, and timestamp.
- **SC-005**: 100% of accountant approve/modify/reject actions on AI suggestions generate an audit event with before/after values.
- **SC-006**: A tenant administrator can view and export their audit log within the application.
- **SC-007**: The landing page passes a mobile-responsive check with no horizontal overflow at 375px viewport width.
- **SC-008**: Sharing the landing page URL on social media displays a branded preview card with title, description, and image.
- **SC-009**: Analytics scripts do not execute until the visitor has given explicit cookie consent (verifiable via browser network tab).
- **SC-010**: The audit log table rejects all UPDATE and DELETE operations (immutability maintained).

## Assumptions

- Legal document content (ToS, Privacy Policy, Acceptable Use) will be provided as Markdown or HTML by the founder. The feature builds the pages and rendering — legal drafting is a separate, non-code task.
- The standard AI disclaimer wording will be: "This is AI-assisted decision support for registered tax agents. It does not constitute tax advice. Professional judgement should always be applied."
- The existing Clerk signup flow can be extended with a post-signup step (redirect to a ToS acceptance page) without modifying Clerk's core configuration.
- The existing `AuditService` and `audit_logs` table are the correct infrastructure for AI suggestion and override logging — no new tables needed, just new event types and consistent usage.
- PostHog is the only product analytics tool. Sentry is error tracking (exempt from consent). Vercel Speed Insights is performance analytics (requires consent).
- The ABN to display in the footer will be provided by the founder.
- The social share image (for OG tags) will be provided or generated as a static asset.
