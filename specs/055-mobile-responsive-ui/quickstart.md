# Quickstart: 055-mobile-responsive-ui

## What This Feature Does

Makes all Clairo frontend screens mobile responsive. The primary change is converting the fixed 256px sidebar in the protected layout into a responsive drawer, then sweeping through all pages to add Tailwind responsive breakpoints to grids, tables, forms, and modals.

## Prerequisites

- Node.js 18+ and npm
- Frontend dev server running: `cd frontend && npm run dev`
- Browser dev tools (Chrome/Firefox) for responsive viewport testing

## Key Files to Modify

### P1 — Layout Shell (1 file, unlocks 33 routes)
- `frontend/src/app/(protected)/layout.tsx` — Convert sidebar to responsive drawer

### P2 — Dashboard & Lists (~5 files)
- `frontend/src/app/(protected)/dashboard/page.tsx` — Minor: pagination
- `frontend/src/app/(protected)/clients/page.tsx` — Minor: pagination
- `frontend/src/app/(protected)/lodgements/page.tsx` — Filter bar wrapping, stat cards
- `frontend/src/app/(protected)/notifications/page.tsx` — Already good, verify
- `frontend/src/app/(protected)/action-items/page.tsx` — Already good, verify

### P3 — Client Detail (2 files)
- `frontend/src/components/client-detail/LedgerCardsHeader.tsx` — Tab bar scroll, action collapse
- `frontend/src/components/client-detail/ClientDetailRedesign.tsx` — Verify grids

### P4 — BAS Workflow (~4 files)
- `frontend/src/components/bas/BASTab.tsx` — Stepper, grids, hero panel, tabs, modals
- `frontend/src/components/bas/ClassificationReview.tsx` — Table column hiding
- `frontend/src/components/bas/TaxCodeSuggestionCard.tsx` — Card layout
- `frontend/src/components/bas/TaxCodeResolutionPanel.tsx` — Table layout

### P5 — Assistant (1 file)
- `frontend/src/app/(protected)/assistant/page.tsx` — History sidebar to Sheet

### P6 — Forms & Modals (~8 files)
- `frontend/src/components/tax-planning/ManualEntryForm.tsx`
- `frontend/src/components/triggers/TriggerFormModal.tsx`
- `frontend/src/components/productivity/DaySummaryModal.tsx`
- `frontend/src/app/(protected)/clients/import/page.tsx`
- `frontend/src/app/(protected)/clients/import/progress/[jobId]/page.tsx`
- `frontend/src/app/(protected)/queries/page.tsx`
- `frontend/src/components/tax-planning/ScenarioCard.tsx`
- `frontend/src/app/(protected)/admin/audit/page.tsx`

### P7 — Xero Reports (~7 files)
- `frontend/src/components/integrations/xero/TrialBalance.tsx`
- `frontend/src/components/integrations/xero/ProfitLoss.tsx`
- `frontend/src/components/integrations/xero/BalanceSheet.tsx`
- `frontend/src/components/integrations/xero/BankSummary.tsx`
- `frontend/src/components/integrations/xero/AgedPayables.tsx`
- `frontend/src/components/integrations/xero/AgedReceivables.tsx`
- `frontend/src/components/integrations/xero/SyncHistory.tsx`

## Reference Pattern

The `PortalHeader.tsx` mobile navigation pattern is the reference:

```tsx
// State
const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

// Desktop nav — hidden on mobile
<nav className="hidden lg:flex">...</nav>

// Mobile hamburger — hidden on desktop
<Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>
  <SheetTrigger asChild className="lg:hidden">
    <Button variant="ghost" size="icon">
      <Menu className="h-5 w-5" />
    </Button>
  </SheetTrigger>
  <SheetContent side="left" className="w-72 p-0">
    {/* Full sidebar content here */}
  </SheetContent>
</Sheet>
```

## Testing

```bash
# Lint
cd frontend && npm run lint

# Typecheck
cd frontend && npx tsc --noEmit
```

Manual testing:
1. Open Chrome DevTools → Toggle Device Toolbar
2. Test at: 375px (iPhone), 414px (iPhone Plus), 768px (iPad portrait), 1024px (iPad landscape)
3. Verify: sidebar hidden, hamburger works, content full-width, tables scroll, grids stack

## Responsive Breakpoints (Tailwind defaults)

| Breakpoint | Width | Use For |
|---|---|---|
| `sm:` | 640px | 2-column grids, button text labels |
| `md:` | 768px | Table column hiding, 3-column grids |
| `lg:` | 1024px | Sidebar show/hide, 4-column grids |
| `xl:` | 1280px | Not commonly needed |

## Key Rules

- Tailwind classes only — no CSS media queries, no JS responsive logic
- Mobile-first: base classes for mobile, prefix for larger screens
- Desktop must be unchanged — zero visual regression at >=1024px
- No new components — modify existing ones with responsive classes
- `cn()` for conditional classes, never string concatenation
