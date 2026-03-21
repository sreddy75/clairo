---
name: clairo-design-system
description: >
  Clairo's UI design system: tokens, component patterns, page layouts, and interaction states.
  Enforces consistent, data-first visual design across all frontend work.
  MUST be used when building or modifying any frontend component, page, or layout.
  Do NOT use for backend-only tasks.
triggers:
  - frontend component
  - page layout
  - UI design
  - redesign
  - styling
  - shadcn
  - tailwind classes
  - dark mode
---

# Clairo Design System

## Design Philosophy

**Data is the hero.** The UI exists to present financial data clearly — everything else gets out of the way.

Inspired by: Ofacc+ (warm minimal accounting), Logiqc (clean data tables), modern B2B SaaS dashboards.

### Core Principles

1. **Data-first**: Numbers, statuses, and content are prominent. UI chrome is minimal.
2. **Warm & clean**: Off-white backgrounds, white cards, generous whitespace. Never cold or sterile.
3. **Strategic color**: Mostly monochrome. Color is reserved for status indicators and primary CTAs only.
4. **Breathable**: Generous spacing between sections. Separation through whitespace, not borders.
5. **Consistent**: Every page uses the same components, tokens, and patterns. No one-off styling.

### Anti-Patterns (NEVER DO)

- Never use raw `<div>`, `<button>`, `<table>` with inline Tailwind — use shadcn/ui components
- Never hardcode hex/hsl values — use CSS variable tokens via Tailwind utilities
- Never create duplicate utility functions (formatCurrency, formatDate, status configs) — import from shared modules
- Never use `gray-*` for dark mode — use `stone-*` consistently
- Never add heavy borders, gradients, or drop shadows for visual separation — use whitespace and subtle background differences
- Never make status colors decorative — color has meaning (green=good, amber=attention, red=urgent)
- Never use more than 2-3 colors in a single chart
- Never add glassmorphism, noise textures, or complex effects to app pages (landing page only)

## Implementation Rules

### Always Use shadcn/ui Components

```tsx
// CORRECT: Use shadcn primitives
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

// WRONG: Raw HTML with inline styles
<div className="bg-white rounded-xl border p-6">
<button className="inline-flex items-center gap-2 px-3 py-2 bg-blue-600...">
```

### Always Use cn() for Conditional Classes

```tsx
import { cn } from "@/lib/utils"

<div className={cn("text-sm", isActive && "font-semibold text-foreground")} />
```

### Always Import Shared Utilities

```tsx
// CORRECT
import { formatCurrency, formatDate, formatPercentage } from "@/lib/formatters"
import { BAS_STATUS_CONFIG } from "@/lib/constants/status"

// WRONG: Defining locally
const formatCurrency = (amount: number) => ...
```

## Reference Files

Read these for detailed specifications:

- `references/ux-patterns.md` — **READ FIRST.** Information architecture, JTBD→page mapping, content hierarchy rules, persona needs. Decides WHAT goes on the page and WHERE.
- `references/design-tokens.md` — Color palette, typography, spacing, shadows. Decides HOW things look.
- `references/component-patterns.md` — Code patterns for every common component type. Decides HOW to build each element.
- `references/page-layouts.md` — Page structure templates (dashboard, list, detail, settings, chat). Decides the overall page STRUCTURE.
