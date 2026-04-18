# Implementation Plan: Mobile Responsive UI

**Branch**: `055-mobile-responsive-ui` | **Date**: 2026-04-09 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/055-mobile-responsive-ui/spec.md`

## Summary

Make all Clairo frontend screens mobile responsive. The primary blocker is the fixed 256px sidebar in the protected layout — converting it to a responsive drawer unlocks mobile access for all 33 protected routes. Then sweep through tables, grids, forms, and modals to add Tailwind responsive breakpoints. Frontend-only — no backend, database, or API changes.

## Technical Context

**Language/Version**: TypeScript 5.x / Next.js 14 (App Router)
**Primary Dependencies**: React 18, Tailwind CSS, shadcn/ui (Sheet, Dialog, Table), lucide-react (icons), Radix UI (primitives)
**Storage**: N/A (frontend-only)
**Testing**: Manual viewport testing (Chrome DevTools), `npm run lint`, `npx tsc --noEmit`
**Target Platform**: Web — mobile browsers (iOS Safari, Chrome Android), tablet browsers, desktop browsers
**Project Type**: Web application (frontend only)
**Performance Goals**: No layout shift on responsive breakpoint transitions; no additional JS bundle for responsive behavior (CSS-only via Tailwind)
**Constraints**: Zero visual regression on desktop (>=1024px); minimum supported viewport 320px; Tailwind breakpoint classes only (no CSS media queries, no JS responsive logic per FR-017)
**Scale/Scope**: ~30 files modified across 7 priority tiers; 33 protected routes + 7 portal routes + public pages

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|---|---|---|
| Module boundaries | PASS | Frontend-only, no cross-module imports |
| Repository pattern | N/A | No database changes |
| Multi-tenancy | N/A | No data access changes |
| Testing strategy | PASS | Manual viewport testing + lint + typecheck; no E2E tests for responsive (Playwright viewport tests deferred) |
| Code quality | PASS | Tailwind classes, `cn()` utility, shadcn/ui components per constitution |
| API design | N/A | No API changes |
| Security | PASS | No new inputs, no auth changes |
| Auditing | N/A | No audit events needed — purely visual changes |
| AI/RAG standards | N/A | No AI changes |
| Layer compliance | PASS | Layer 2 constitution says "Mobile-responsive design" — this spec fulfills that requirement |

**Post-Phase-1 Re-check**: All gates still pass. No data model or API contracts generated (frontend-only).

## Project Structure

### Documentation (this feature)

```text
specs/055-mobile-responsive-ui/
├── plan.md              # This file
├── research.md          # Phase 0 output — responsive audit findings
├── quickstart.md        # Phase 1 output — developer quickstart
└── tasks.md             # Phase 2 output (created by /speckit.tasks)
```

No `data-model.md` or `contracts/` — this is a frontend-only spec with no new entities or API endpoints.

### Source Code (files to modify)

```text
frontend/src/
├── app/
│   ├── (protected)/
│   │   ├── layout.tsx              # P1: Sidebar → responsive drawer
│   │   ├── dashboard/page.tsx      # P2: Pagination responsive
│   │   ├── clients/
│   │   │   ├── page.tsx            # P2: Pagination responsive
│   │   │   └── import/
│   │   │       ├── page.tsx        # P6: grid-cols-3 → responsive
│   │   │       └── progress/[jobId]/page.tsx  # P6: grid-cols-4 → responsive
│   │   ├── lodgements/page.tsx     # P2: Filter bar, stat cards
│   │   ├── queries/page.tsx        # P6: grid-cols-3 → responsive
│   │   ├── assistant/page.tsx      # P5: History sidebar → Sheet
│   │   └── admin/audit/page.tsx    # P6: Fixed-width column
│   └── ...
├── components/
│   ├── client-detail/
│   │   └── LedgerCardsHeader.tsx   # P3: Tab bar overflow-x-auto, action collapse
│   ├── bas/
│   │   ├── BASTab.tsx              # P4: Stepper, grids, hero, tabs, modals
│   │   ├── ClassificationReview.tsx # P4: Table column hiding
│   │   ├── TaxCodeSuggestionCard.tsx # P4: Card layout
│   │   └── TaxCodeResolutionPanel.tsx # P4: Table layout
│   ├── tax-planning/
│   │   ├── ManualEntryForm.tsx     # P6: grid-cols → responsive
│   │   ├── ScenarioCard.tsx        # P6: grid-cols-3 → responsive
│   │   └── TaxPlanningWorkspace.tsx # P6: Modal full-screen on mobile
│   ├── triggers/
│   │   └── TriggerFormModal.tsx    # P6: Form grids → responsive
│   ├── productivity/
│   │   └── DaySummaryModal.tsx     # P6: grid-cols-4 → responsive
│   └── integrations/xero/
│       ├── TrialBalance.tsx        # P7: Table column hiding
│       ├── ProfitLoss.tsx          # P7: Table column hiding
│       ├── BalanceSheet.tsx        # P7: Table column hiding
│       ├── BankSummary.tsx         # P7: Table column hiding
│       ├── AgedPayables.tsx        # P7: Table column hiding
│       ├── AgedReceivables.tsx     # P7: Table column hiding
│       ├── SyncHistory.tsx         # P7: Table column hiding
│       └── ReportSelector.tsx      # P7: Fixed-width triggers → responsive
└── ...
```

**Structure Decision**: No new files. All changes are modifications to existing components adding Tailwind responsive utility classes.

## Implementation Design

### Phase 1: Responsive Layout Shell (P1 — User Story 1)

**File**: `frontend/src/app/(protected)/layout.tsx`

**Current state**: Fixed sidebar `w-64` (line 344), content offset `pl-64` (line 492), skeleton also hardcoded (lines 310, 321). Zero responsive classes.

**Changes**:

1. **Add state for mobile menu**:
   ```tsx
   const [sidebarOpen, setSidebarOpen] = useState(false);
   ```

2. **Add imports**:
   ```tsx
   import { Sheet, SheetContent, SheetTrigger } from "@/components/ui/sheet";
   import { Menu } from "lucide-react";
   ```

3. **Desktop sidebar — hide on mobile** (line 344):
   ```tsx
   // Before:
   <aside className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border flex flex-col z-30">
   // After:
   <aside className="fixed inset-y-0 left-0 w-64 bg-card border-r border-border hidden lg:flex flex-col z-30">
   ```

4. **Mobile sidebar drawer** — add Sheet wrapping the same nav content, visible only below `lg`:
   ```tsx
   <Sheet open={sidebarOpen} onOpenChange={setSidebarOpen}>
     <SheetContent side="left" className="w-72 p-0 flex flex-col">
       {/* Same sidebar content: logo, nav links, admin section, settings, help */}
       {/* Each nav link onClick also calls setSidebarOpen(false) */}
     </SheetContent>
   </Sheet>
   ```

5. **Content area — responsive offset** (line 492):
   ```tsx
   // Before:
   <div className="pl-64">
   // After:
   <div className="lg:pl-64">
   ```

6. **Mobile header bar** — add hamburger button to the existing header (line 494):
   ```tsx
   <header className="sticky top-0 z-20 h-14 bg-card border-b ...">
     <div className="flex items-center justify-between h-full px-4">
       {/* Left side: hamburger (mobile only) + logo (mobile only) */}
       <div className="flex items-center gap-2 lg:hidden">
         <Button variant="ghost" size="icon" onClick={() => setSidebarOpen(true)}>
           <Menu className="h-5 w-5" />
         </Button>
         <ClairoLogo className="h-6" />
       </div>
       {/* Right side: existing theme toggle, notifications, user button */}
       <div className="flex items-center gap-2 ml-auto">
         <ThemeToggle />
         <NotificationBell ... />
         <UserButton ... />
       </div>
     </div>
   </header>
   ```

7. **Skeleton state** — same responsive treatment (lines 310, 321):
   ```tsx
   // Sidebar skeleton: add hidden lg:flex
   // Content skeleton: change pl-64 to lg:pl-64
   ```

**Key detail**: The `NavLink` component (lines 87-117) and the nav items array (lines 66-83) are reused for both the desktop sidebar and the mobile Sheet drawer. Extract the sidebar content into a shared fragment or inline it in both places. The mobile version adds `onClick={() => setSidebarOpen(false)}` to each NavLink.

**Breakpoint rationale**: `lg:` (1024px) per research.md — the sidebar has 8 nav + 5 admin items; on 768px tablet the sidebar would leave only 512px for content, too cramped for data tables.

---

### Phase 2: Dashboard & List Pages (P2 — User Story 2)

**Changes are minor** — these pages already have good responsive handling.

#### Dashboard (`dashboard/page.tsx`)
- Stat cards: Already `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4` (line 394) — no change
- Table columns: Already hide 3 columns at `md:`/`lg:` — no change
- Filter bar: Already stacks at `sm:` — no change
- **Fix needed**: Pagination bar (line 684) — add responsive padding and wrapping

#### Clients list (`clients/page.tsx`)
- Header/filters: Already responsive — no change
- Table: Already hides 2 columns — no change
- **Fix needed**: Pagination bar (line 312) — same as dashboard

#### Lodgements (`lodgements/page.tsx`)
- Stat cards: `grid-cols-2 lg:grid-cols-5` (line 277) — **change to** `grid-cols-1 sm:grid-cols-2 lg:grid-cols-5` for very narrow phones
- Filter bar: Outer stacks at `sm:` but inner filter group (line 332) doesn't wrap — **add** `flex-wrap` to the inner `<div className="flex items-center gap-2">`
- Select triggers: `w-[130px]` (lines 335, 349) — **change to** `w-full sm:w-[130px]`
- Table: Hides 1 column — **hide** "Days Left" column on mobile too (it duplicates Due Date info)

#### Notifications, Action Items, Feedback
- Already have responsive stat grids and column hiding — **verify only**, no changes expected

---

### Phase 3: Client Detail & Tabs (P3 — User Story 3)

**File**: `frontend/src/components/client-detail/LedgerCardsHeader.tsx`

**Current state**: Already the most responsive component (uses `sm:`, `lg:` for padding/sizing). Key gap is the tab bar.

**Changes**:

1. **Tab bar** (line 462): Add horizontal scroll:
   ```tsx
   // Before:
   <div className="flex items-center gap-1 overflow-visible">
   // After:
   <div className="flex items-center gap-1 overflow-x-auto scrollbar-hide">
   ```
   Add `-webkit-overflow-scrolling: touch` via Tailwind or a utility class.

2. **Client header actions** (line 389): Collapse secondary actions on mobile:
   ```tsx
   // Secondary action buttons: add hidden sm:inline-flex
   // Keep primary CTA always visible
   ```

3. **Client header layout**: The `flex items-start justify-between` (line 370) already stacks reasonably due to responsive padding. Verify at 375px — may need `flex-col sm:flex-row` if the two sides (client info + actions) overlap.

---

### Phase 4: BAS Workflow (P4 — User Story 4)

**File**: `frontend/src/components/bas/BASTab.tsx` (1954 lines)

This is the most complex phase. Changes are surgical — add responsive classes without restructuring the component.

1. **Workflow stepper** (line 777-807):
   - Step labels: Add `hidden sm:inline` to `<span>` text at line 793
   - Step containers: Reduce padding on mobile: `px-2 sm:px-3 py-1 sm:py-1.5`
   - Arrow separators: Add `hidden sm:block` to hide arrows on mobile, or reduce size
   - Add `overflow-x-auto` to the parent flex container as a safety net

2. **Hero summary panel** (line 815):
   - Change `flex items-start justify-between` to `flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4`
   - BAS field stats row (line 841): Change `flex items-center gap-6` to `flex flex-wrap items-center gap-3 sm:gap-6`

3. **GST details grids** (lines 1225, 1250, 1269):
   - `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`
   - `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`

4. **PAYG tab grid** (line 1308):
   - `grid-cols-3` → `grid-cols-1 sm:grid-cols-3`

5. **Tab headers** (line 1174):
   - Add `overflow-x-auto` to the flex container
   - Add `flex-shrink-0` to each tab button to prevent compression

6. **Adjustment form** (lines 1564, 1600):
   - `grid-cols-2` → `grid-cols-1 sm:grid-cols-2`

7. **Transaction detail modal** (line 1746):
   - `max-w-3xl mx-4` → `w-full sm:max-w-3xl mx-2 sm:mx-4`
   - Transaction items (line 1821): `flex items-center gap-4 ml-4` → `flex flex-col sm:flex-row sm:items-center gap-2 sm:gap-4 ml-2 sm:ml-4`

8. **Export buttons** (line 894):
   - `flex items-center gap-2` → `flex flex-wrap items-center gap-2`
   - Individual button text: Add `hidden sm:inline` to text labels, keep icons always visible

**File**: `frontend/src/components/bas/ClassificationReview.tsx`

1. **Table column hiding** (lines 259-264):
   - Hide "Date" column: `hidden md:table-cell` on header (line 259) and body cells
   - Hide "Client Said" column: `hidden lg:table-cell` on header (line 262) and body cells at line 294
   - Always visible: Amount, Description, AI Suggests, Action (4 columns on mobile)

---

### Phase 5: AI Assistant (P5 — User Story 5)

**File**: `frontend/src/app/(protected)/assistant/page.tsx`

1. **History sidebar** (line 610): On mobile, render as Sheet instead of inline:
   ```tsx
   // Desktop: existing inline aside (hidden on mobile)
   <aside className="hidden lg:flex w-72 border-r border-border bg-card flex-col flex-shrink-0">
   
   // Mobile: Sheet overlay
   <Sheet open={showHistory} onOpenChange={setShowHistory}>
     <SheetContent side="left" className="w-72 p-0">
       {/* Same history content */}
     </SheetContent>
   </Sheet>
   ```

2. **History toggle button** (line 578): Already exists. On mobile, ensure `showHistory` defaults to `false`.

3. **Chat input** (bottom of page): Verify it stays visible when mobile keyboard opens. The existing `sticky bottom-0` or equivalent should handle this. May need `pb-safe` for iOS Safari safe area.

---

### Phase 6: Forms, Modals & Grids (P6 — User Story 6)

Mechanical sweep — apply responsive breakpoints to all remaining fixed grids and modals.

| File | Current | Change To |
|---|---|---|
| `ManualEntryForm.tsx:99` | `grid-cols-2` | `grid-cols-1 sm:grid-cols-2` |
| `ManualEntryForm.tsx:110` | `grid-cols-2` | `grid-cols-1 sm:grid-cols-2` |
| `ManualEntryForm.tsx:121` | `grid-cols-3` | `grid-cols-1 sm:grid-cols-3` |
| `TriggerFormModal.tsx:317` | `grid-cols-2` | `grid-cols-1 sm:grid-cols-2` |
| `TriggerFormModal.tsx:399` | `grid-cols-3` | `grid-cols-1 sm:grid-cols-3` |
| `TriggerFormModal.tsx:478` | `grid-cols-2` | `grid-cols-1 sm:grid-cols-2` |
| `DaySummaryModal.tsx:251` | `grid-cols-4` | `grid-cols-2 sm:grid-cols-4` |
| `clients/import/page.tsx:249` | `grid-cols-3` | `grid-cols-1 sm:grid-cols-3` |
| `import/progress/.../page.tsx:234` | `grid-cols-4` | `grid-cols-2 sm:grid-cols-4` |
| `queries/page.tsx:425` | `grid-cols-3` | `grid-cols-1 sm:grid-cols-3` |
| `ScenarioCard.tsx:68` | `grid-cols-3` | `grid-cols-1 sm:grid-cols-3` |
| `admin/audit/page.tsx` | `w-[160px]` col | `w-auto` or remove fixed width |

**Modals**: For all custom modals using `max-w-Nxl` patterns:
- `TaxPlanningWorkspace.tsx:1018`: Add `w-full sm:max-w-4xl` and `h-full sm:max-h-[90vh] sm:rounded-2xl` for full-screen on mobile
- `DaySummaryModal.tsx:173`: Same pattern — `w-full sm:max-w-2xl`
- `admin/knowledge/view-content-modal.tsx:102`: Same pattern

---

### Phase 7: Xero Reports & Secondary Tables (P7 — User Story 7)

All 7 Xero report components use raw `<table>` elements. The approach:

1. **Ensure `overflow-auto` wrapper** exists on all report table containers (add `<div className="overflow-x-auto">` if missing)

2. **Column hiding** pattern per report:
   - Trial Balance: Hide "Account Code" column on mobile, keep Account Name + Amount
   - P&L: Hide percentage columns on mobile
   - Balance Sheet: Hide comparative period columns on mobile
   - Bank Summary: Hide account number on mobile
   - Aged Payables/Receivables: Hide older aging buckets on mobile (keep Current + 30+ days)
   - Sync History: Hide detailed status on mobile

3. **ReportSelector.tsx**: Change `w-[240px]` (line 154) to `w-full sm:w-[240px]` and `w-[180px]` (line 345) to `w-full sm:w-[180px]`

## Complexity Tracking

No constitution violations. All changes use existing technology (Tailwind CSS, shadcn/ui Sheet component). No new dependencies, no new components, no new patterns. The only complexity is the volume of files (~30) but each change is mechanical and low-risk.

## Risk Assessment

| Risk | Impact | Mitigation |
|---|---|---|
| Desktop visual regression | High | All responsive classes are additive (mobile-first). Desktop classes unchanged. Test at 1024px+ for every modified file. |
| BASTab complexity | Medium | Component is 1954 lines. Changes are surgical Tailwind class additions, not structural refactoring. |
| Sheet z-index conflict with sidebar | Low | Sheet is `z-50`, sidebar is `z-30`. Sheet always overlays correctly. |
| Mobile keyboard hiding chat input | Low | Test on real iOS Safari. May need `pb-safe` or `env(safe-area-inset-bottom)`. |
| Table column hiding removes important data | Medium | Only hide truly redundant columns (e.g., "Days Left" when "Due Date" exists). Essential data always visible. |

## Dependencies

- No backend dependencies
- No external package additions
- Depends on existing `Sheet` component from shadcn/ui (already installed)
- Depends on existing `Menu` icon from lucide-react (already installed)
