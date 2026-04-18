# Tasks: Mobile Responsive UI

**Input**: Design documents from `/specs/055-mobile-responsive-ui/`
**Prerequisites**: plan.md, spec.md, research.md, quickstart.md

**Tests**: Not included — spec specifies manual viewport testing via Chrome DevTools, plus lint and typecheck validation.

**Organization**: Tasks grouped by user story (7 stories). Each story is independently implementable and testable. All changes are Tailwind class modifications to existing files — no new files, no backend changes.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- All file paths relative to `frontend/src/`

---

## Phase 0: Git Setup (REQUIRED)

- [x] T000 Create feature branch from main
  - Run: `git checkout -b 055-mobile-responsive-ui`
  - _Already complete — branch exists_

---

## Phase 1: Setup

**Purpose**: No new dependencies or project structure needed. Verify existing Sheet component and imports are available.

- [x] T001 Verify Sheet component supports `side="left"` in `frontend/src/components/ui/sheet.tsx`
  - Confirm `sheetVariants` includes `left` variant with `w-3/4 border-r sm:max-w-sm`
  - Confirm exports: `Sheet`, `SheetContent`, `SheetTrigger`, `SheetHeader`, `SheetTitle`
  - No modifications expected — verification only

---

## Phase 2: Foundational

**Purpose**: No blocking prerequisites — all user stories modify independent files. Proceed directly to user story phases.

**Checkpoint**: Ready for user story implementation.

---

## Phase 3: User Story 1 — Responsive Navigation & Layout Shell (Priority: P1) MVP

**Goal**: Convert the fixed 256px sidebar into a responsive drawer. On mobile (<1024px), hide the sidebar, show a hamburger menu in the header that opens a Sheet-based navigation drawer. Desktop unchanged.

**Independent Test**: Open any protected page on a 375px viewport. Content spans full width. Hamburger opens nav drawer. All nav links work. Desktop (>=1024px) unchanged.

### Implementation

- [x] T002 [US1] Add mobile sidebar state and imports in `app/(protected)/layout.tsx`
  - Add `useState` for `sidebarOpen` / `setSidebarOpen`
  - Add imports: `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle` from `@/components/ui/sheet`
  - Add import: `Menu` from `lucide-react`
  - Add import: `Button` from `@/components/ui/button` (if not already imported)

- [x] T003 [US1] Hide desktop sidebar on mobile in `app/(protected)/layout.tsx`
  - Line ~344: Change `<aside className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border flex flex-col z-30">` to add `hidden lg:flex` (replacing `flex` with `hidden lg:flex`)
  - This hides the sidebar on viewports <1024px

- [x] T004 [US1] Add mobile Sheet drawer with navigation in `app/(protected)/layout.tsx`
  - Add a `<Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>` component
  - Use `<SheetContent side="left" className="w-72 p-0 flex flex-col">`
  - Include `<SheetHeader>` with `<SheetTitle>` containing the ClairoLogo for accessibility
  - Duplicate the sidebar content inside the Sheet: navigation links, admin section, settings, help
  - Add `onClick={() => setSidebarOpen(false)}` to each `NavLink` inside the Sheet to auto-close on navigation
  - Ensure admin section expand/collapse works inside Sheet
  - Ensure feature-gated nav items respect the same `canAccess` checks

- [x] T005 [US1] Make content area responsive in `app/(protected)/layout.tsx`
  - Line ~492: Change `<div className="pl-64">` to `<div className="lg:pl-64">`
  - This allows content to span full width on mobile

- [x] T006 [US1] Add mobile header with hamburger menu in `app/(protected)/layout.tsx`
  - In the existing `<header>` (line ~494), restructure to include:
    - Left side (`lg:hidden`): hamburger `<Button variant="ghost" size="icon">` with `<Menu>` icon that calls `setSidebarOpen(true)`, plus `<ClairoLogo>` wordmark
    - Right side (`ml-auto`): existing `<ThemeToggle>`, `<NotificationBell>`, `<UserButton>`
  - Ensure header height remains `h-14`
  - Ensure `sticky top-0 z-20` is preserved

- [x] T007 [US1] Make skeleton loading state responsive in `app/(protected)/layout.tsx`
  - Line ~310: Add `hidden lg:flex` to the skeleton sidebar `<aside>`
  - Line ~321: Change skeleton content `pl-64` to `lg:pl-64`
  - Add a simplified mobile skeleton header with hamburger placeholder for `lg:hidden`

- [x] T008 [US1] Verify desktop layout is unchanged at >=1024px in `app/(protected)/layout.tsx`
  - Manual test: Open dashboard at 1280px viewport — sidebar visible, content offset, header as before
  - Manual test: Open dashboard at 1024px — sidebar just visible (lg breakpoint)
  - Manual test: Open dashboard at 1023px — sidebar hidden, hamburger visible
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`

**Checkpoint**: All 33 protected routes now render full-width on mobile. Navigation accessible via hamburger drawer. Desktop unchanged.

---

## Phase 4: User Story 2 — Dashboard & List Pages on Mobile (Priority: P2)

**Goal**: Ensure dashboard, clients, lodgements, notifications, and action items pages are usable on mobile. Fix pagination, filter bars, and remaining column visibility.

**Independent Test**: Open `/dashboard`, `/clients`, `/lodgements` on 375px viewport. Stat cards stack. Tables show essential columns only. Filters stack vertically. No horizontal overflow.

### Implementation

- [x] T009 [P] [US2] Fix dashboard pagination responsiveness in `app/(protected)/dashboard/page.tsx`
  - Pagination bar (line ~684): Add `flex-wrap` and responsive padding `px-3 sm:px-6`
  - Page info text: Consider `hidden sm:inline` for verbose text, show compact version on mobile
  - Verify: stat cards, table, and filters already responsive — no changes needed for those

- [x] T010 [P] [US2] Fix clients list pagination responsiveness in `app/(protected)/clients/page.tsx`
  - Pagination bar (line ~312): Same treatment as dashboard — `flex-wrap`, responsive padding
  - Verify: header, filters, and table column hiding already responsive

- [x] T011 [P] [US2] Fix lodgements page responsive issues in `app/(protected)/lodgements/page.tsx`
  - Stat cards grid (line ~277): Change `grid-cols-2 lg:grid-cols-5` to `grid-cols-1 sm:grid-cols-2 lg:grid-cols-5`
  - Filter bar inner group (line ~332): Add `flex-wrap` to `<div className="flex items-center gap-2">`
  - Select triggers (lines ~335, ~349): Change `w-[130px]` to `w-full sm:w-[130px]`
  - Table: Add `hidden md:table-cell` to "Days Left" column header and body cells (duplicates Due Date info)
  - Pagination: Same responsive treatment as dashboard

- [x] T012 [P] [US2] Verify notifications page responsive state in `app/(protected)/notifications/page.tsx`
  - Confirm: stat cards grid already responsive (`grid-cols-2 lg:grid-cols-4`)
  - Confirm: table already hides 2 columns on mobile
  - Fix any pagination bar issues if present

- [x] T013 [P] [US2] Verify action items page responsive state in `app/(protected)/action-items/page.tsx`
  - Confirm: stat cards grid already responsive (`grid-cols-2 sm:grid-cols-4`)
  - Fix any pagination or filter bar issues if present

**Checkpoint**: All primary list pages usable on mobile. Stat cards stack, tables show essential columns, filters don't overflow.

---

## Phase 5: User Story 3 — Client Detail & Tabs on Mobile (Priority: P3)

**Goal**: Make client detail header and tab bar work on mobile. Tab bar scrolls horizontally. Header stacks. Secondary actions collapse.

**Independent Test**: Open `/clients/[id]` on 375px viewport. Client name visible. Tab bar scrolls horizontally. Tapping tabs works. Overview cards in 2-column grid.

### Implementation

- [x] T014 [US3] Add horizontal scroll to tab bar in `components/client-detail/LedgerCardsHeader.tsx`
  - Tab bar container (line ~462): Change `overflow-visible` to `overflow-x-auto` and add `scrollbar-hide` class
  - Add `flex-shrink-0` to each tab button to prevent compression
  - Add `scroll-smooth` for smooth scroll behavior on touch devices
  - Verify: dropdown tab groups ("Data", "More") still work with overflow

- [x] T015 [US3] Collapse secondary header actions on mobile in `components/client-detail/LedgerCardsHeader.tsx`
  - Action buttons area (line ~389): Add `hidden sm:inline-flex` to secondary action buttons (e.g., Refresh)
  - Keep primary CTA (e.g., "New BAS" or "Analyze") always visible
  - Verify client header layout (line ~370): If client info + actions overlap at 375px, change to `flex-col sm:flex-row`

- [x] T016 [US3] Verify client detail body grids in `components/client-detail/ClientDetailRedesign.tsx`
  - Check grid at line ~647 (`grid-cols-1 md:grid-cols-2 lg:grid-cols-4`) — already responsive, verify only
  - Check TrafficLightDashboard (`grid-cols-2 lg:grid-cols-4`) — already responsive, verify only

**Checkpoint**: Client detail page navigable on mobile. Tab bar scrolls. Header doesn't overflow.

---

## Phase 6: User Story 4 — BAS Workflow on Mobile (Priority: P4)

**Goal**: Make BAS workflow usable on mobile for review/monitoring. Compact stepper, stacked summary, responsive grids, scrollable tables.

**Independent Test**: Open a BAS session on 375px viewport. Stepper shows active step. Summary figures readable. Transaction table scrollable. Modals don't overflow.

### Implementation

- [x] T017 [US4] Make workflow stepper compact on mobile in `components/bas/BASTab.tsx`
  - Step labels (line ~793): Add `hidden sm:inline` to `<span>` text — show only icon/number on mobile
  - Step containers (line ~785): Change padding to `px-2 sm:px-3 py-1 sm:py-1.5`
  - Arrow separators (line ~799): Add `hidden sm:block` to `<ArrowRight>` icons
  - Parent container (line ~777): Add `overflow-x-auto` as safety net

- [x] T018 [US4] Stack hero summary panel on mobile in `components/bas/BASTab.tsx`
  - Hero panel (line ~815): Change `flex items-start justify-between` to `flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4`
  - BAS field stats row (line ~841): Change `flex items-center gap-6` to `flex flex-wrap items-center gap-3 sm:gap-6`
  - Export buttons (line ~894): Change to `flex flex-wrap items-center gap-2`
  - Export button text labels: Add `hidden sm:inline` to text, keep icons always visible

- [x] T019 [US4] Make GST/PAYG/adjustment grids responsive in `components/bas/BASTab.tsx`
  - GST Sales grid (line ~1225): Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`
  - GST Purchases grid (line ~1250): Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`
  - GST Summary grid (line ~1269): Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`
  - PAYG grid (line ~1308): Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`
  - Adjustment form grids (lines ~1564, ~1600): Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`

- [x] T020 [US4] Make BAS tab headers scrollable in `components/bas/BASTab.tsx`
  - Tab header container (line ~1174): Add `overflow-x-auto` to the flex container
  - Each tab button (line ~1188): Add `flex-shrink-0` to prevent compression

- [x] T021 [US4] Make transaction detail modal responsive in `components/bas/BASTab.tsx`
  - Modal container (line ~1746): Change `max-w-3xl mx-4` to `w-full sm:max-w-3xl mx-2 sm:mx-4`
  - Transaction items (line ~1821): Change `flex items-center gap-4 ml-4` to `flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 ml-2 sm:ml-4`

- [x] T022 [P] [US4] Hide non-essential columns in classification table in `components/bas/ClassificationReview.tsx`
  - Date column header (line ~259): Add `hidden md:table-cell`
  - Date column body cells: Add matching `hidden md:table-cell`
  - "Client Said" column header (line ~262): Add `hidden lg:table-cell`
  - "Client Said" column body cells (line ~294): Add matching `hidden lg:table-cell`
  - Verify: Amount, Description, AI Suggests, Action always visible (4 columns on mobile)

- [x] T023 [P] [US4] Verify TaxCodeSuggestionCard mobile layout in `components/bas/TaxCodeSuggestionCard.tsx`
  - Check fixed-width cells (`max-w-[220px]`, `max-w-[140px]`) — ensure table has `overflow-x-auto` wrapper
  - Add responsive column hiding if table has >4 columns on mobile

- [x] T024 [P] [US4] Verify TaxCodeResolutionPanel mobile layout in `components/bas/TaxCodeResolutionPanel.tsx`
  - Check table structure — ensure `overflow-x-auto` wrapper exists
  - Add responsive column hiding for non-essential columns

**Checkpoint**: BAS workflow navigable on mobile. Stepper compact. Grids stack. Tables scrollable. Modals fit viewport.

---

## Phase 7: User Story 5 — AI Assistant Chat on Mobile (Priority: P5)

**Goal**: Hide history sidebar on mobile, show as Sheet overlay. Chat input stays visible with mobile keyboard.

**Independent Test**: Open `/assistant` on 375px viewport. Chat area is full width. History toggle opens Sheet overlay. Chat input usable.

### Implementation

- [x] T025 [US5] Convert history sidebar to responsive Sheet in `app/(protected)/assistant/page.tsx`
  - Add imports: `Sheet`, `SheetContent`, `SheetHeader`, `SheetTitle` from `@/components/ui/sheet`
  - Desktop sidebar (line ~610): Add `hidden lg:flex` to `<aside className="w-72 ...">`
  - Add mobile Sheet: `<Sheet open={showHistory && isMobile} onOpenChange={setShowHistory}>` with `<SheetContent side="left" className="w-72 p-0">` containing the same history content
  - Use a CSS-only approach: render both desktop aside (`hidden lg:flex`) and mobile Sheet, with Sheet only opening when `showHistory` is true and viewport is <lg
  - Alternative simpler approach: just add `hidden lg:flex` to the aside, and wrap history content in a Sheet that's always rendered but only opens when `showHistory` is true on mobile — the Sheet component handles its own open/close state

- [x] T026 [US5] Ensure chat input works with mobile keyboard in `app/(protected)/assistant/page.tsx`
  - Verify chat input container uses `sticky bottom-0` or equivalent positioning
  - If needed, add `pb-safe` or `pb-[env(safe-area-inset-bottom)]` for iOS Safari safe area
  - Test: on 375px viewport, the chat input should be visible and usable

**Checkpoint**: AI assistant fully functional on mobile. History accessible via Sheet. Chat input works.

---

## Phase 8: User Story 6 — Forms, Modals & Grids on Mobile (Priority: P6)

**Goal**: Mechanical sweep — add responsive breakpoints to all remaining fixed grids, forms, and modals.

**Independent Test**: Open any page with forms/modals/grids on 375px viewport. Forms single-column. Modals full-width. Grids stack.

### Implementation

- [x] T027 [P] [US6] Make ManualEntryForm grids responsive in `components/tax-planning/ManualEntryForm.tsx`
  - Line ~99: Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`
  - Line ~110: Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`
  - Line ~121: Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`

- [x] T028 [P] [US6] Make TriggerFormModal grids responsive in `components/triggers/TriggerFormModal.tsx`
  - Line ~317: Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`
  - Line ~399: Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`
  - Line ~478: Change `grid-cols-2` to `grid-cols-1 sm:grid-cols-2`

- [x] T029 [P] [US6] Make DaySummaryModal responsive in `components/productivity/DaySummaryModal.tsx`
  - Grid (line ~251): Change `grid-cols-4` to `grid-cols-2 sm:grid-cols-4`
  - Modal container (line ~173): Change to `w-full sm:max-w-2xl` and add `sm:rounded-2xl` for full-screen on mobile

- [x] T030 [P] [US6] Make client import pages responsive in `app/(protected)/clients/import/page.tsx` and `app/(protected)/clients/import/progress/[jobId]/page.tsx`
  - `import/page.tsx` (line ~249): Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`
  - `progress/[jobId]/page.tsx` (line ~234): Change `grid-cols-4` to `grid-cols-2 sm:grid-cols-4`

- [x] T031 [P] [US6] Make queries page grid responsive in `app/(protected)/queries/page.tsx`
  - Line ~425: Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`

- [x] T032 [P] [US6] Make ScenarioCard grid responsive in `components/tax-planning/ScenarioCard.tsx`
  - Line ~68: Change `grid-cols-3` to `grid-cols-1 sm:grid-cols-3`

- [x] T033 [P] [US6] Make TaxPlanningWorkspace modal responsive in `components/tax-planning/TaxPlanningWorkspace.tsx`
  - Modal container (line ~1018): Change to `w-full sm:max-w-4xl h-full sm:max-h-[90vh] sm:rounded-2xl`

- [x] T034 [P] [US6] Fix audit page fixed-width column in `app/(protected)/admin/audit/page.tsx`
  - Remove or replace `w-[160px]` fixed column width with `w-auto` or responsive width

- [x] T035 [P] [US6] Make knowledge view-content modal responsive in `app/(protected)/admin/knowledge/components/view-content-modal.tsx`
  - Modal container (line ~102): Change to `w-full sm:max-w-4xl h-full sm:max-h-[90vh] sm:rounded-2xl`

**Checkpoint**: All fixed grids now have responsive breakpoints. Modals go full-screen on mobile. Forms stack single-column.

---

## Phase 9: User Story 7 — Xero Reports & Secondary Tables on Mobile (Priority: P7)

**Goal**: Ensure Xero report tables have overflow scroll and report selector dropdowns work on mobile. Add column hiding where meaningful.

**Independent Test**: Open a client's Xero reports tab on 375px viewport. Report selector dropdowns are full-width and tappable. Tables scroll horizontally. Key columns visible.

### Implementation

- [x] T036 [P] [US7] Make ReportSelector dropdowns responsive in `components/integrations/xero/ReportSelector.tsx`
  - Line ~154: Change `w-[240px]` to `w-full sm:w-[240px]`
  - Line ~345: Change `w-[180px]` to `w-full sm:w-[180px]`

- [x] T037 [P] [US7] Add overflow-x-auto to Trial Balance table in `components/integrations/xero/TrialBalance.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide "Account Code" column on mobile: add `hidden md:table-cell` to header and body cells
  - Keep Account Name + Amount always visible

- [x] T038 [P] [US7] Add overflow-x-auto to Profit & Loss table in `components/integrations/xero/ProfitLoss.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide percentage columns on mobile: add `hidden md:table-cell`

- [x] T039 [P] [US7] Add overflow-x-auto to Balance Sheet table in `components/integrations/xero/BalanceSheet.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide comparative period columns on mobile: add `hidden md:table-cell`

- [x] T040 [P] [US7] Add overflow-x-auto to BankSummary table in `components/integrations/xero/BankSummary.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide account number on mobile: add `hidden md:table-cell`

- [x] T041 [P] [US7] Add overflow-x-auto to AgedPayables table in `components/integrations/xero/AgedPayables.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide older aging buckets on mobile (keep Current + 30+ days): add `hidden md:table-cell`

- [x] T042 [P] [US7] Add overflow-x-auto to AgedReceivables table in `components/integrations/xero/AgedReceivables.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide older aging buckets on mobile: add `hidden md:table-cell`

- [x] T043 [P] [US7] Add overflow-x-auto to SyncHistory table in `components/integrations/xero/SyncHistory.tsx`
  - Ensure table is wrapped in `<div className="overflow-x-auto">`
  - Hide detailed status column on mobile: add `hidden md:table-cell`

**Checkpoint**: All Xero report tables scrollable on mobile. Selectors full-width. Key columns visible.

---

## Phase 10: Polish & Cross-Cutting Concerns

**Purpose**: Final validation and cleanup across all modified files.

- [x] T044 Run lint and typecheck across all changes
  - Run: `cd frontend && npm run lint`
  - Run: `cd frontend && npx tsc --noEmit`
  - Fix any errors

- [x] T045 Grep audit: verify no unresponsive grid-cols remain
  - Run: `grep -rn "grid-cols-[2-9]" frontend/src/ --include="*.tsx" | grep -v "sm:\|md:\|lg:\|xl:"` to find any remaining `grid-cols-N` without responsive prefixes
  - Fix any remaining instances

- [x] T046 Verify desktop regression at 1024px+ across key pages
  - Manual test at 1280px: dashboard, clients, client detail, BAS, assistant, lodgements, settings
  - Verify: sidebar visible, content offset correct, no layout shifts, all functionality intact

- [x] T047 Verify mobile experience at 375px across key pages
  - Manual test at 375px: dashboard, clients, client detail, BAS, assistant, lodgements
  - Verify: hamburger menu works, content full-width, tables scrollable, grids stacked, modals full-screen

- [x] T048 Verify tablet experience at 768px across key pages
  - Manual test at 768px: dashboard, clients, client detail
  - Verify: hamburger menu (since <1024px), 2-column grids where appropriate, tables show more columns than 375px

---

## Phase FINAL: PR & Merge (REQUIRED)

- [ ] TFINAL-1 Ensure lint and typecheck pass
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - All checks must pass before PR

- [ ] TFINAL-2 Push feature branch and create PR
  - Run: `git push -u origin 055-mobile-responsive-ui`
  - Run: `gh pr create --title "Spec 055: Mobile Responsive UI" --body "..."`
  - Include summary: layout shell, list pages, client detail, BAS, assistant, forms/modals, Xero reports

- [ ] TFINAL-3 Address review feedback (if any)

- [ ] TFINAL-4 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-5 Update ROADMAP.md
  - Mark spec 055 as COMPLETE in the spec registry

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: Complete — branch exists
- **Phase 1 (Setup)**: Verification only — no blocking work
- **Phase 2 (Foundational)**: Empty — no blocking prerequisites
- **Phase 3 (US1 — Layout Shell)**: **MUST complete first** — all other stories depend on the sidebar being responsive, otherwise testing mobile layouts is meaningless
- **Phases 4-9 (US2-US7)**: Can proceed **in parallel** after Phase 3 completes — each modifies different files
- **Phase 10 (Polish)**: After all user stories complete
- **Phase FINAL (PR)**: After polish complete

### User Story Dependencies

- **US1 (Layout Shell)**: No dependencies. **MVP — must complete first.** All other stories require this.
- **US2 (Dashboard & Lists)**: Depends on US1 (layout must be responsive to test)
- **US3 (Client Detail)**: Depends on US1. Independent of US2.
- **US4 (BAS Workflow)**: Depends on US1. Independent of US2, US3.
- **US5 (AI Assistant)**: Depends on US1. Independent of US2-US4.
- **US6 (Forms & Modals)**: Depends on US1. Independent of US2-US5.
- **US7 (Xero Reports)**: Depends on US1. Independent of US2-US6.

### Parallel Opportunities

**After US1 completes, ALL of these can run in parallel:**

```
US1 (DONE) ──┬── US2 (dashboard/lists — 5 files)
              ├── US3 (client detail — 2 files)
              ├── US4 (BAS workflow — 4 files)
              ├── US5 (assistant — 1 file)
              ├── US6 (forms/modals — 9 files)
              └── US7 (Xero reports — 8 files)
```

**Within each story, tasks marked [P] can run in parallel** — they modify different files with no cross-dependencies.

---

## Implementation Strategy

### MVP First (US1 Only)

1. Complete T001-T008 (Layout Shell)
2. **STOP and VALIDATE**: Test at 375px, 768px, 1024px, 1280px
3. This alone makes all 33 routes usable on mobile

### Incremental Delivery

1. US1 (Layout Shell) → Test → **Mobile access unlocked**
2. US2 (Dashboard & Lists) → Test → **Primary pages polished**
3. US3 (Client Detail) → Test → **Core workflow navigable**
4. US4 (BAS Workflow) → Test → **Core product usable on mobile**
5. US5 (AI Assistant) → Test → **Chat works on mobile**
6. US6 (Forms & Modals) → Test → **Quality-of-life sweep done**
7. US7 (Xero Reports) → Test → **All pages polished**
8. Polish → PR → Merge

### Parallel Strategy

With multiple agents:
1. Complete US1 together (single file, sequential tasks)
2. After US1: launch US2-US7 in parallel (all modify different files)
3. Converge at Phase 10 (Polish)

---

## Summary

| Metric | Value |
|---|---|
| **Total tasks** | 48 + 5 final = 53 |
| **US1 (Layout Shell)** | 7 tasks |
| **US2 (Dashboard & Lists)** | 5 tasks |
| **US3 (Client Detail)** | 3 tasks |
| **US4 (BAS Workflow)** | 8 tasks |
| **US5 (AI Assistant)** | 2 tasks |
| **US6 (Forms & Modals)** | 9 tasks |
| **US7 (Xero Reports)** | 8 tasks |
| **Setup + Polish** | 6 tasks |
| **Files modified** | ~30 |
| **New files** | 0 |
| **Parallel opportunities** | US2-US7 all parallel after US1; [P] tasks within each story |
| **MVP scope** | US1 only (7 tasks, 1 file) |
