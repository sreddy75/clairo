# Research: Mobile Responsive UI

**Feature**: 055-mobile-responsive-ui
**Date**: 2026-04-09

## Research Questions & Findings

### 1. What is the current responsive state of the protected layout?

**Finding**: The protected layout (`(protected)/layout.tsx`) has **zero responsive classes** anywhere on the sidebar or content area. The sidebar is `fixed inset-y-0 left-0 w-64` (line 344) with content offset `pl-64` (line 492). The loading skeleton state also hardcodes `w-64` (line 310) and `pl-64` (line 321). No `hidden`, `md:flex`, `lg:`, or any breakpoint-prefixed class exists.

### 2. What existing mobile nav pattern can be reused?

**Finding**: `PortalHeader.tsx` implements a complete mobile navigation pattern:
- State: `const [mobileMenuOpen, setMobileMenuOpen] = useState(false)`
- Desktop nav: `hidden md:flex`
- Mobile trigger: `<Button>` with `<Menu>` icon, class `md:hidden`
- Drawer: `<Sheet open={mobileMenuOpen} onOpenChange={setMobileMenuOpen}>` with `<SheetContent side="right" className="w-80">`
- Auto-close: Each nav link calls `setMobileMenuOpen(false)` on click

**Decision**: Follow this exact pattern for the protected sidebar, but use `side="left"` (since the sidebar is on the left) and `lg:` breakpoint (1024px) instead of `md:` (768px) because the protected sidebar has more navigation items and admin sections.

### 3. What Sheet component configuration is needed?

**Finding**: The Sheet component (`ui/sheet.tsx`) already supports `side="left"` with default classes `inset-y-0 left-0 h-full w-3/4 border-r sm:max-w-sm`. The width can be overridden via `className`. The z-index is `z-50` (higher than the sidebar's `z-30`).

**Decision**: Use `<SheetContent side="left" className="w-72 p-0">` to match the sidebar width aesthetic. The `p-0` removes default padding so the sidebar content can control its own padding.

### 4. Which pages already have responsive handling?

**Finding**:
| Page | State | Details |
|---|---|---|
| Dashboard | Good | Stat grids responsive, table hides 3 columns, header stacks |
| Clients list | Good | Header stacks, table hides 2 columns |
| Lodgements | Partial | Stat cards 2-col, but filter bar inner row doesn't wrap, only 1 column hides |
| Notifications | Good | Hides 2 columns |
| Action items | Good | Stat cards responsive |
| Feedback | Good | Stat cards responsive |
| BASTab | None | 1954 lines, zero responsive classes anywhere |
| ClassificationReview | None | 6-column raw table, all always visible |
| ManualEntryForm | None | grid-cols-2 and grid-cols-3 with no breakpoints |
| Assistant | None | w-72 sidebar, no responsive handling |
| LedgerCardsHeader | Good | Best responsive example: responsive padding, icon sizing, button text hiding |

### 5. What is the best approach for the BAS workflow stepper on mobile?

**Alternatives considered**:
1. **Horizontal scroll** — Wrap stepper in `overflow-x-auto`, keep all steps visible with scroll
2. **Step number only** — Show "Step 2 of 5" text on mobile, hide the full stepper
3. **Compact icons** — Show only step numbers/icons without text labels on mobile

**Decision**: Compact approach — hide step text labels on mobile (`hidden sm:inline`), show only step number/icon. This keeps all 5 steps visible as small circles/badges without needing horizontal scroll. Fallback to "Step X of Y" text if even the compact version is too wide.

### 6. What is the right breakpoint for sidebar show/hide?

**Alternatives considered**:
1. `md:` (768px) — Matches PortalHeader pattern
2. `lg:` (1024px) — Standard desktop breakpoint

**Decision**: `lg:` (1024px). The protected sidebar contains 8 nav items + 5 admin items + settings + help. On a 768px tablet in portrait, showing a 256px sidebar leaves only 512px for content — too cramped for data tables. The spec already calls for `lg:` in FR-001.

### 7. Should we use `useDeviceContext` or Tailwind breakpoints?

**Finding**: `useDeviceContext` exists with `MOBILE_BREAKPOINT=640` and `TABLET_BREAKPOINT=1024`, but it's JS-based (not SSR-compatible without hydration mismatch risk) and is only used in 2 places (both A2UI-related).

**Decision**: Use Tailwind breakpoint classes exclusively per FR-017. They work with SSR, don't cause hydration mismatches, and are the existing pattern in all responsive components. The `useDeviceContext` hook is not expanded or promoted.

### 8. What about the assistant page sidebar?

**Finding**: The assistant page has a `w-72` history sidebar (line 610) that's JS-toggled via `showHistory` state. It uses `{showHistory && <aside>}` conditional rendering. The page header has a History toggle button (line 578) with the only responsive class: `hidden sm:inline` on the button text.

**Decision**: On mobile (<lg), default `showHistory` to `false` and when toggled on, render the history as a Sheet overlay (same pattern as the main sidebar). This can reuse the existing `showHistory` state — just change the rendering to use Sheet on mobile and inline on desktop.

### 9. What about fixed-width Select triggers?

**Finding**: Multiple pages use `w-[130px]`, `w-[180px]`, `w-[240px]` on SelectTrigger components. These are problematic on mobile where screen space is limited.

**Decision**: Add responsive classes like `w-full sm:w-[130px]` so they fill available space on mobile but keep their fixed width on desktop. This is a mechanical find-and-replace across ~8 instances.
