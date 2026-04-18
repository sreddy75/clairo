# Feature Specification: Mobile Responsive UI

**Feature Branch**: `055-mobile-responsive-ui`
**Created**: 2026-04-09
**Status**: Draft
**Input**: Make all screens mobile responsive. The UI currently does not render on mobile screens well — it's almost useless. The protected layout has a fixed 256px sidebar that leaves ~119px of content space on a 375px phone. Tables overflow, grids break, and core workflows are inaccessible on mobile devices.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Responsive Navigation & Layout Shell (Priority: P1)

An accountant opens Clairo on their phone (or tablet). Instead of a permanently visible 256px sidebar crushing the content area, they see a full-width content area with a top header bar. A hamburger menu button in the header opens a slide-out drawer containing the full navigation menu, user info, and settings links. The drawer closes when the user taps outside it, selects a nav item, or taps the close button. On desktop (>=1024px), the sidebar remains as-is — no visual change for existing desktop users.

This is the single highest-priority item because every one of the 33 protected routes inherits the `(protected)/layout.tsx` layout. Until the sidebar is responsive, no protected page is usable on mobile.

**Why this priority**: This one change unblocks mobile access for all 33 protected routes. Without it, nothing else matters — content is literally 119px wide on a phone.

**Independent Test**: Open any protected page (e.g., `/dashboard`, `/clients`, `/lodgements`) on a 375px viewport. The full content area is visible. The sidebar is hidden. A hamburger menu opens the navigation drawer. All nav links work from the drawer.

**Acceptance Scenarios**:

1. **Given** a user on a viewport <1024px, **When** they load any protected page, **Then** the sidebar is hidden and the content area spans the full viewport width.
2. **Given** a user on a viewport <1024px, **When** they tap the hamburger menu icon in the top header, **Then** a slide-out Sheet drawer opens from the left showing the full navigation menu.
3. **Given** the navigation drawer is open, **When** the user taps a nav item, **Then** they navigate to that page and the drawer closes automatically.
4. **Given** the navigation drawer is open, **When** the user taps outside the drawer (the overlay), **Then** the drawer closes.
5. **Given** a user on a viewport >=1024px, **When** they load any protected page, **Then** the fixed sidebar displays exactly as it does today — zero visual regression.
6. **Given** a user on a viewport <1024px, **When** the page header renders, **Then** it includes the hamburger menu button, the Clairo logo/wordmark, and key action icons (notifications bell, user avatar).
7. **Given** a user rotates their phone from portrait to landscape (>1024px), **When** the viewport crosses the breakpoint, **Then** the layout switches from mobile (hamburger + drawer) to desktop (fixed sidebar) without a page reload.

---

### User Story 2 — Dashboard & List Pages on Mobile (Priority: P2)

An accountant checks their dashboard on their phone during commute. Stat cards stack into a single column on small screens, two columns on medium screens. The client list table hides non-essential columns (sync status, last activity date) on mobile, showing only the client name, status badge, and an action menu. The dashboard action items, recent notifications, and key metrics are all readable and tappable on a phone screen.

Similar treatment applies to the other primary list pages: clients list, lodgements list, notifications list, and action items.

**Why this priority**: Dashboard and list views are the most-visited pages. Accountants checking status on their phone is the primary mobile use case.

**Independent Test**: Open `/dashboard` on a 375px viewport. All stat cards are visible (stacked 1-column). The clients table shows client name + status + actions. No horizontal overflow. All interactive elements (links, buttons, dropdowns) have adequate tap targets (>=44px).

**Acceptance Scenarios**:

1. **Given** a user on a viewport <640px viewing the dashboard, **When** the stat cards render, **Then** they display in a single column layout.
2. **Given** a user on a viewport 640px-1023px viewing the dashboard, **When** the stat cards render, **Then** they display in a two-column grid.
3. **Given** a user on a viewport <768px viewing the clients list, **When** the table renders, **Then** columns "Last Activity" and "Last Synced" are hidden, showing only Name, Status, and Actions.
4. **Given** a user on a viewport <768px viewing the lodgements list, **When** the table renders, **Then** non-essential columns (period, entity type) are hidden, showing obligation name, status, and due date.
5. **Given** a user on a viewport <768px viewing the notifications list, **When** the table renders, **Then** the client column is hidden and notifications show type, message, and timestamp.
6. **Given** any list page on mobile, **When** filter/search controls render, **Then** they stack vertically and Select triggers expand to full width instead of fixed pixel widths (no `w-[180px]`).
7. **Given** any interactive element on mobile (button, link, dropdown trigger), **When** the user attempts to tap it, **Then** the tap target is at least 44x44px per Apple HIG / Material guidelines.

---

### User Story 3 — Client Detail & Tabs on Mobile (Priority: P3)

An accountant opens a specific client's detail page on their phone. The tab navigation (Overview, BAS, Tax Planning, Assets, etc.) is horizontally scrollable rather than wrapping or overflowing. The active tab is visible. The client header stacks vertically: client name on top, status badges below, action buttons below that. The traffic-light status cards display in a 2-column grid (already responsive) and remain usable.

**Why this priority**: The client detail page is where accountants spend the most time. The tab bar and header layout are the key mobile barriers.

**Independent Test**: Open `/clients/[id]` on a 375px viewport. The client name and status are visible without truncation. The tab bar scrolls horizontally. Tapping a tab loads the correct content. The overview status cards are visible in a 2-column grid.

**Acceptance Scenarios**:

1. **Given** a user on mobile viewing a client detail page, **When** the header renders, **Then** the client name, status badges, and action buttons stack vertically with adequate spacing.
2. **Given** a user on mobile viewing a client detail page, **When** the tab bar renders, **Then** it is horizontally scrollable with `overflow-x-auto` and no wrapping, and the active tab is scrolled into view.
3. **Given** a user on mobile viewing the client overview tab, **When** the traffic-light dashboard renders, **Then** status cards display in a 2-column grid (this already works via existing responsive classes).
4. **Given** a user on mobile viewing the client overview tab, **When** financial summary cards render, **Then** they stack vertically instead of in a multi-column grid.
5. **Given** action buttons in the client header (e.g., "New BAS", "Sync"), **When** on mobile, **Then** secondary actions collapse into a dropdown/overflow menu, keeping only the primary CTA visible.

---

### User Story 4 — BAS Workflow on Mobile (Priority: P4)

An accountant reviews a BAS session on their phone. The 5-step workflow progress indicator adapts for mobile — either as a compact horizontal scroll with step numbers (hiding full labels) or as a "Step 2 of 5: Transaction Review" text indicator. The BAS summary panel stacks vertically. Transaction tables in the classification review show essential columns only (description, amount, tax code, action) with other columns hidden. The transaction drill-down stacks amount and tax code vertically rather than side-by-side.

This is the most complex component (`BASTab.tsx`, 1954 lines) and the core product workflow, but it ranks P4 because BAS preparation is primarily a desk-based workflow — mobile access is for review/monitoring, not primary data entry.

**Why this priority**: BAS is the core product, but accountants doing detailed transaction classification will be at their desk. Mobile BAS access is for checking session status and reviewing AI suggestions — not full-screen data entry.

**Independent Test**: Open a BAS session on a 375px viewport. The workflow stepper is visible and shows which step is active. The BAS summary figures are readable. The transaction table scrolls horizontally if needed. AI suggestion cards are tappable and readable.

**Acceptance Scenarios**:

1. **Given** a user on mobile viewing a BAS session, **When** the workflow stepper renders, **Then** it shows a compact representation (step numbers without full labels, or a "Step X of 5" text indicator) that fits within the viewport.
2. **Given** a user on mobile viewing the BAS summary, **When** the BAS fields panel renders, **Then** fields stack vertically (label, amount, GST on separate lines) rather than in a wide table row.
3. **Given** a user on mobile viewing the transaction review, **When** the classification table renders, **Then** it shows Description, Amount, and Tax Code columns, with other columns hidden behind `hidden md:table-cell`.
4. **Given** a user on mobile viewing a tax code suggestion card, **When** the card renders, **Then** the suggested code, confidence indicator, and approve/reject buttons are all visible and tappable without horizontal scrolling.
5. **Given** a user on mobile viewing the BAS tab, **When** any modal or dialog opens (e.g., transaction detail, override reason), **Then** the modal renders full-width on mobile with adequate padding.

---

### User Story 5 — AI Assistant Chat on Mobile (Priority: P5)

An accountant asks the AI assistant a quick tax question on their phone. The chat history sidebar (`w-72` fixed width) is hidden on mobile, replaced by a toggle button or top bar. The chat input is pinned to the bottom of the viewport (mobile keyboard-friendly). Chat messages use full width. The assistant response with citations is readable without horizontal scroll.

**Why this priority**: The AI assistant is a high-value quick-access feature on mobile — asking a quick tax question while away from desk is a natural mobile use case.

**Independent Test**: Open `/assistant` on a 375px viewport. The chat history sidebar is hidden. A button toggles it as a Sheet overlay. The chat input is visible and usable. Sending a message and receiving a response works. Citations are readable.

**Acceptance Scenarios**:

1. **Given** a user on mobile viewing the assistant page, **When** the page renders, **Then** the conversation history sidebar is hidden and the chat area spans full width.
2. **Given** a user on mobile viewing the assistant page, **When** they tap a "History" toggle button, **Then** the conversation history opens as a Sheet overlay from the left.
3. **Given** a user on mobile typing in the chat input, **When** the mobile keyboard opens, **Then** the chat input remains visible and pinned above the keyboard (not pushed off-screen).
4. **Given** a user on mobile reading an assistant response with citations, **When** the response renders, **Then** citation cards stack vertically and are fully readable without horizontal scrolling.

---

### User Story 6 — Forms, Modals & Grids on Mobile (Priority: P6)

All multi-column form layouts stack to single-column on mobile. All Dialogs and custom modals render full-screen on viewports <640px (instead of floating `max-w-lg` centered cards). All grid layouts that use fixed `grid-cols-N` without responsive breakpoints are updated to start at `grid-cols-1` and scale up. Fixed-width elements (`w-[240px]`, `w-[180px]`) on Select triggers and inputs use `w-full` on mobile.

This is a mechanical sweep across ~15 files to add responsive breakpoints.

**Why this priority**: These are quality-of-life fixes that prevent cramped, overflowing, or clipped content on mobile. Lower priority because they don't block core workflows — the horizontal scroll fallback from `overflow-auto` on tables makes them usable, just not pleasant.

**Independent Test**: Open any page with forms, modals, or grids on a 375px viewport. Forms use single-column layout. Modals fill the screen. Grids don't overflow. No content is clipped or hidden behind overflow.

**Acceptance Scenarios**:

1. **Given** a user on mobile opening a form (e.g., ManualEntryForm, TriggerFormModal, RequestForm), **When** the form renders, **Then** all form fields stack in a single column — no side-by-side fields on viewports <640px.
2. **Given** a user on mobile opening a Dialog or modal, **When** the modal renders on a viewport <640px, **Then** it uses full viewport width and height (or near-full with small margin), not a floating card.
3. **Given** any page with `grid-cols-N` where N>1 and no responsive prefix, **When** viewed on mobile, **Then** the grid starts at `grid-cols-1` and scales up at `sm:` or `md:` breakpoints.
4. **Given** any Select trigger or input with a fixed pixel width (e.g., `w-[180px]`), **When** viewed on mobile, **Then** it uses `w-full` or a responsive width instead.
5. **Given** the client import progress page (`grid-cols-4`), **When** viewed on mobile, **Then** stats display in `grid-cols-2` or `grid-cols-1` instead of 4 across.
6. **Given** the queries page (`grid-cols-3`), **When** viewed on mobile, **Then** cards display in `grid-cols-1` stacking vertically.

---

### User Story 7 — Xero Reports & Secondary Tables on Mobile (Priority: P7)

The 7 Xero report components (Trial Balance, Profit & Loss, Balance Sheet, Bank Summary, Aged Payables, Aged Receivables, Sync History) and secondary data tables (Assets, Purchase Orders, Depreciation, Billing History) all render acceptably on mobile. These tables are already wrapped in `overflow-auto` providing horizontal scroll as a baseline. The improvement is: add `hidden md:table-cell` to non-essential columns where meaningful, ensure the table container has adequate horizontal scroll indicators, and ensure the report selector dropdowns work on mobile.

**Why this priority**: These are reference/reporting views, not primary workflows. Horizontal scroll already works as a fallback. This is polish.

**Independent Test**: Open a client's Xero reports tab on a 375px viewport. The report selector dropdown works. The report table is scrollable. Key columns (account name, amount) are always visible.

**Acceptance Scenarios**:

1. **Given** a user on mobile viewing Xero reports, **When** the report selector renders, **Then** both selector dropdowns (report type, date range) are full-width and tappable.
2. **Given** a user on mobile viewing a Xero report table, **When** the table has more columns than fit on screen, **Then** the table scrolls horizontally with a visible scroll indicator.
3. **Given** a user on mobile viewing the Trial Balance or P&L report, **When** the table renders, **Then** the Account Name and Amount columns are always visible; other columns are hidden on mobile.
4. **Given** a user on mobile viewing the assets or purchase orders list, **When** the table renders, **Then** essential columns (name, value, status) are visible and non-essential columns are hidden.

---

### Edge Cases

- What happens when an accountant is mid-BAS-review on desktop and switches to their phone (e.g., leaves the office)? The page should render correctly on the phone viewport without losing BAS session state — session state is server-side, not dependent on viewport.
- What happens on a tablet in portrait mode (~768px)? The layout should use the mobile drawer navigation (since <1024px) but can show 2-column grids where appropriate — tablet is explicitly in the "mobile navigation" range.
- What happens when the mobile keyboard opens on the assistant chat or search inputs? The input should remain visible and the viewport should not jump or clip content. Use `position: sticky` or `position: fixed` with keyboard-aware bottom padding.
- What happens on very small screens (<320px, e.g., iPhone SE first gen)? Content should not break. Minimum supported viewport is 320px. Below that, horizontal scroll is acceptable.
- What happens when a user zooms in on mobile (pinch-to-zoom)? The root layout already sets `userScalable: false` and `maximumScale: 1` — this prevents zoom. This is intentional for the app-like experience but should be noted as a design decision.
- What happens with the notification bell and real-time updates on mobile? The notification dropdown should render full-width on mobile instead of as a fixed-width popover.

## Requirements *(mandatory)*

### Functional Requirements

**Navigation & Layout**

- **FR-001**: The protected layout MUST hide the fixed sidebar on viewports <1024px and display a hamburger menu that opens a Sheet-based navigation drawer.
- **FR-002**: The navigation drawer MUST contain all navigation items, user info, and settings links currently in the sidebar.
- **FR-003**: The mobile header bar MUST include: hamburger menu button, Clairo logo, notification bell, and user avatar.
- **FR-004**: The desktop layout (>=1024px) MUST remain unchanged — zero visual regression for existing desktop users.
- **FR-005**: Layout transitions between mobile and desktop MUST work correctly on viewport resize and device rotation without requiring a page reload.

**Tables & Data Display**

- **FR-006**: All data tables MUST remain horizontally scrollable on mobile via the existing `overflow-auto` wrapper.
- **FR-007**: Primary list tables (clients, lodgements, notifications, action items) MUST hide non-essential columns on viewports <768px using `hidden md:table-cell`.
- **FR-008**: Filter controls and Select triggers MUST NOT use fixed pixel widths on mobile — they MUST expand to full width or use responsive sizing.

**Grids & Forms**

- **FR-009**: All `grid-cols-N` (where N>1) without responsive breakpoint prefixes MUST be updated to include mobile-first breakpoints (starting at `grid-cols-1`).
- **FR-010**: Multi-column form layouts MUST stack to single-column on viewports <640px.
- **FR-011**: Dialogs and modals MUST render full-width on viewports <640px.

**Component-Specific**

- **FR-012**: The client detail tab bar MUST be horizontally scrollable on mobile with `overflow-x-auto`.
- **FR-013**: The BAS workflow stepper MUST display a compact mobile representation that fits within 375px.
- **FR-014**: The AI assistant page MUST hide the conversation history sidebar on mobile and provide a toggle to show it as a Sheet overlay.
- **FR-015**: All interactive elements (buttons, links, dropdown triggers) MUST have minimum tap targets of 44x44px on mobile.

**Responsive Breakpoints (Tailwind conventions)**

- **FR-016**: The responsive breakpoints MUST follow Tailwind's default breakpoints: `sm` (640px), `md` (768px), `lg` (1024px), `xl` (1280px). No custom breakpoints.
- **FR-017**: All responsive changes MUST use Tailwind utility classes exclusively — no CSS media queries, no JS-based responsive logic (except the existing `useDeviceContext` hook where already used).

### Key Entities

No new data models or database changes. This is a frontend-only spec.

## Auditing & Compliance Checklist *(mandatory)*

### Audit Events Required

- [ ] **Authentication Events**: No changes to authentication flows.
- [ ] **Data Access Events**: No changes to data access patterns.
- [ ] **Data Modification Events**: No data modifications — frontend-only changes.
- [ ] **Integration Events**: No integration changes.
- [ ] **Compliance Events**: No compliance impact.

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|---|---|---|---|---|
| No new audit events | Frontend-only visual changes | N/A | N/A | N/A |

### Compliance Considerations

- **ATO Requirements**: No impact — no changes to data display accuracy, calculation logic, or audit trails.
- **Data Retention**: No changes.
- **Access Logging**: No changes.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All 33 protected routes render with full-width content on a 375px viewport — no content crushed by the sidebar.
- **SC-002**: Navigation is fully functional on mobile via the hamburger drawer — all nav links reachable.
- **SC-003**: Zero visual regression on desktop (>=1024px) — the sidebar, header, and all layouts render identically to current state.
- **SC-004**: All primary list pages (dashboard, clients, lodgements, notifications, action items) are usable on mobile — key information visible without horizontal scrolling.
- **SC-005**: All interactive elements on mobile have tap targets >=44px.
- **SC-006**: No `grid-cols-N` (N>1) exists without a responsive breakpoint prefix (verified by grep).
- **SC-007**: The BAS workflow page is navigable on mobile — stepper visible, session status readable, transaction table scrollable.
- **SC-008**: The AI assistant chat is functional on mobile — messages send and receive, history accessible via drawer.
- **SC-009**: All Dialogs and custom modals render full-width on mobile viewports (<640px).
- **SC-010**: Lighthouse mobile usability score >=90 on the dashboard page.

## Assumptions

- The minimum supported mobile viewport width is 320px (iPhone SE). Below that, horizontal scrolling is acceptable.
- The existing `useDeviceContext` hook will NOT be expanded as the primary responsive mechanism — Tailwind breakpoint classes are preferred for consistency and SSR compatibility.
- The existing Sheet component from shadcn/ui is already configured for mobile-friendly drawer behavior (`w-3/4 sm:max-w-sm`) and will be used for the navigation drawer.
- The PortalHeader component's mobile navigation pattern (hamburger + Sheet) is the reference implementation to follow for the protected layout.
- Desktop users will see zero visual changes — this spec is additive responsive behavior only.
- The landing page (`/`), auth pages, onboarding flow, portal layout, and legal pages are already mobile-responsive and are out of scope for this spec.
- No new components need to be created — this spec modifies existing layouts and components with responsive Tailwind classes.
- The BAS workflow on mobile is for review/monitoring, not primary data entry. Full transaction classification is expected to happen on desktop. The mobile BAS experience prioritizes readability over editability.
- Tablet (768px-1023px) uses mobile navigation (hamburger drawer) but can display 2-column grids. The breakpoint for sidebar visibility is `lg` (1024px).
