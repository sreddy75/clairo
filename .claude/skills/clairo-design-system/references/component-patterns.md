# Component Patterns

Every pattern below uses shadcn/ui primitives. NEVER recreate these with raw HTML.

---

## Stat Card (Hero Numbers)

The most important component — displays KPIs with the number as the visual hero.

```tsx
import { Card, CardContent } from "@/components/ui/card"
import { formatCurrency } from "@/lib/formatters"
import { cn } from "@/lib/utils"
import { TrendingUp, TrendingDown } from "lucide-react"

interface StatCardProps {
  label: string
  value: string | number
  trend?: { value: number; isPositive: boolean }
  subtitle?: string
}

function StatCard({ label, value, trend, subtitle }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4">
        <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </p>
        <p className="mt-2 text-2xl font-bold tracking-tight tabular-nums">
          {value}
        </p>
        {trend && (
          <div className="mt-2 flex items-center gap-1 text-sm">
            {trend.isPositive ? (
              <TrendingUp className="h-4 w-4 text-status-success" />
            ) : (
              <TrendingDown className="h-4 w-4 text-status-danger" />
            )}
            <span className={cn(
              "font-medium tabular-nums",
              trend.isPositive
                ? "text-status-success"
                : "text-status-danger"
            )}>
              {trend.value}%
            </span>
            {subtitle && (
              <span className="text-muted-foreground">{subtitle}</span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  )
}
```

**Key rules:**
- Number is `text-2xl font-bold tabular-nums` — biggest element in the card (professional density)
- Label is `text-xs uppercase tracking-wide text-muted-foreground` — small, above the number
- Trend arrow + percentage below the number
- Card has `p-4` padding (compact), no inner header/footer separation
- Grid: `gap-3` between stat cards, `grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`
- ALL numbers MUST have `tabular-nums` — no exceptions

---

## Data Table

Clean, scannable tables with minimal decoration.

```tsx
import {
  Table, TableBody, TableCell, TableHead,
  TableHeader, TableRow,
} from "@/components/ui/table"
import { Badge } from "@/components/ui/badge"

<Card>
  <CardHeader className="flex flex-row items-center justify-between pb-4">
    <CardTitle className="text-lg font-semibold">Client List</CardTitle>
    <div className="flex items-center gap-2">
      {/* Filter/search controls */}
    </div>
  </CardHeader>
  <CardContent className="p-0">
    <Table>
      <TableHeader>
        <TableRow className="hover:bg-transparent">
          <TableHead className="text-xs font-medium text-muted-foreground">Name</TableHead>
          <TableHead className="text-xs font-medium text-muted-foreground">Status</TableHead>
          <TableHead className="text-right text-xs font-medium text-muted-foreground">Amount</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        <TableRow>
          <TableCell className="font-medium">Acme Pty Ltd</TableCell>
          <TableCell>
            <StatusDot status="overdue" />
          </TableCell>
          <TableCell className="text-right tabular-nums">
            {formatCurrency(12500)}
          </TableCell>
        </TableRow>
      </TableBody>
    </Table>
  </CardContent>
</Card>
```

**Key rules:**
- Table lives inside a Card with `CardContent className="p-0"` (table provides its own padding)
- Column headers are `text-xs font-medium text-muted-foreground`
- Numbers right-aligned with `tabular-nums`
- Row hover is subtle (`hover:bg-muted/50`)
- No zebra striping — clean white rows
- Status shown with StatusDot (colored dot + text), not colored backgrounds

---

## Status Dot

Minimal status indicator inspired by Logiqc reference.

```tsx
import { cn } from "@/lib/utils"

const STATUS_CONFIG = {
  overdue:    { dot: "bg-red-600",    text: "text-red-600    dark:text-red-400",    label: "Overdue" },
  due_soon:   { dot: "bg-amber-500",  text: "text-amber-600  dark:text-amber-400",  label: "Due Soon" },
  due_later:  { dot: "bg-yellow-500", text: "text-yellow-600 dark:text-yellow-400", label: "Due Later" },
  on_track:   { dot: "bg-emerald-600",text: "text-emerald-600 dark:text-emerald-400",label: "On Track" },
  complete:   { dot: "bg-emerald-600",text: "text-emerald-600 dark:text-emerald-400",label: "Complete" },
  draft:      { dot: "bg-stone-400",  text: "text-stone-500  dark:text-stone-400",  label: "Draft" },
  in_progress:{ dot: "bg-blue-600",   text: "text-blue-600   dark:text-blue-400",   label: "In Progress" },
} as const

function StatusDot({ status }: { status: keyof typeof STATUS_CONFIG }) {
  const config = STATUS_CONFIG[status]
  return (
    <span className="inline-flex items-center gap-1.5 text-sm">
      <span className={cn("h-2 w-2 shrink-0 rounded-full", config.dot)} />
      <span className={cn("font-medium", config.text)}>{config.label}</span>
    </span>
  )
}
```

**Key rule:** The dot is `h-2 w-2 rounded-full` — small, precise, color carries the meaning.

---

## Page Header

Every page starts with the same header pattern.

```tsx
<div className="flex items-center justify-between">
  <div>
    <h1 className="text-xl font-semibold tracking-tight">Dashboard</h1>
    <p className="mt-1 text-sm text-muted-foreground">
      Overview of your practice performance
    </p>
  </div>
  <div className="flex items-center gap-3">
    {/* Action buttons */}
    <Button variant="outline" size="sm">Export</Button>
    <Button size="sm">Add Client</Button>
  </div>
</div>
```

**Key rules:**
- Title is `text-xl font-semibold tracking-tight` — one per page (professional density)
- Subtitle is `text-sm text-muted-foreground` — optional
- Action buttons right-aligned, primary action last (rightmost)
- `gap-3` between buttons

---

## Section Label

Uppercase section headers like Ofacc+ reference.

```tsx
<p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
  Invoice Details
</p>
```

Use to group related form fields or content sections within a card.

---

## Filter Bar

Tab filters with counts (Logiqc style).

```tsx
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Search } from "lucide-react"

<div className="flex items-center justify-between gap-4">
  <div className="flex items-center gap-1 rounded-lg bg-muted p-1">
    <Button
      variant={activeTab === "all" ? "secondary" : "ghost"}
      size="sm"
      className="h-8 text-xs"
    >
      All <span className="ml-1 text-muted-foreground">45</span>
    </Button>
    <Button
      variant={activeTab === "in_progress" ? "secondary" : "ghost"}
      size="sm"
      className="h-8 text-xs"
    >
      In Progress <span className="ml-1 text-muted-foreground">43</span>
    </Button>
    <Button
      variant={activeTab === "closed" ? "secondary" : "ghost"}
      size="sm"
      className="h-8 text-xs"
    >
      Closed <span className="ml-1 text-muted-foreground">2</span>
    </Button>
  </div>

  <div className="relative w-72">
    <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
    <Input placeholder="Search..." className="pl-9 h-9" />
  </div>
</div>
```

**Key rules:**
- Tab container has `rounded-lg bg-muted p-1` — subtle background grouping
- Active tab uses `variant="secondary"`, inactive uses `variant="ghost"`
- Counts shown inline in `text-muted-foreground`
- Search input has icon prefix, right-aligned

---

## Alert Card

Card-based notifications with icon + action (alerts reference).

```tsx
import { Card, CardContent } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { ArrowRight } from "lucide-react"

<Card>
  <CardContent className="flex items-center gap-6 p-6">
    <div className="flex h-14 w-14 shrink-0 items-center justify-center rounded-2xl bg-amber-50 dark:bg-amber-500/10">
      <AlertTriangle className="h-7 w-7 text-amber-600 dark:text-amber-400" />
    </div>
    <div className="flex-1 min-w-0">
      <h3 className="font-semibold">Payment Attention Needed</h3>
      <p className="mt-1 text-sm text-muted-foreground">
        Your payment requires your attention. Please review your payment details.
      </p>
    </div>
    <Button className="shrink-0">
      Fix <ArrowRight className="ml-1 h-4 w-4" />
    </Button>
  </CardContent>
</Card>
```

**Key rules:**
- Icon container: `h-14 w-14 rounded-2xl` with light semantic background color
- Text: Bold heading + muted description
- Action button right-aligned
- Layout: `flex items-center gap-6`

---

## Chart Container

Consistent wrapper for all Recharts components.

```tsx
<Card>
  <CardHeader className="flex flex-row items-center justify-between pb-2">
    <CardTitle className="text-lg font-semibold">Revenue Trend</CardTitle>
    <div className="flex items-center gap-2">
      <Button variant="outline" size="sm" className="h-8 text-xs">
        Jan - Dec, 2026
      </Button>
      <Button variant="outline" size="sm" className="h-8 text-xs">
        Full Stats
      </Button>
    </div>
  </CardHeader>
  <CardContent>
    <div className="flex items-baseline gap-2 mb-6">
      <span className="text-2xl font-bold tracking-tight tabular-nums">
        {formatCurrency(bestValue)}
      </span>
      <span className="text-sm text-muted-foreground">
        as of {bestMonth}
      </span>
    </div>
    {/* Recharts component here */}
    <div className="mt-4 flex items-center gap-6 text-sm">
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--chart-1))]" />
        <span className="text-muted-foreground">GST Collected</span>
      </div>
      <div className="flex items-center gap-2">
        <span className="h-2.5 w-2.5 rounded-full bg-[hsl(var(--chart-2))]" />
        <span className="text-muted-foreground">GST Paid</span>
      </div>
    </div>
  </CardContent>
</Card>
```

**Key rules:**
- Hero number displayed prominently ABOVE the chart
- Date range selector in top-right as outline buttons
- Legend below the chart with colored dots (not Recharts default legend)
- Chart colors: max 2-3, using `--chart-1` and `--chart-2` tokens

---

## Form Fields

Clean, minimal form fields.

```tsx
import { Label } from "@/components/ui/label"
import { Input } from "@/components/ui/input"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"

<div className="space-y-1.5">
  <Label className="text-xs font-medium text-muted-foreground">
    Company name
  </Label>
  <Input value="Dominik Tyka" />
</div>

<div className="space-y-1.5">
  <Label className="text-xs font-medium text-muted-foreground">
    Document type
  </Label>
  <Select>
    <SelectTrigger>
      <SelectValue placeholder="Select..." />
    </SelectTrigger>
    <SelectContent>
      <SelectItem value="vat">VAT Invoice</SelectItem>
    </SelectContent>
  </Select>
</div>
```

**Key rules:**
- Label is `text-xs font-medium text-muted-foreground` — small, above the field
- `space-y-1.5` between label and input
- Group related fields with Section Labels above them
- Two-column field layouts use `grid grid-cols-2 gap-4`

---

## Quick-Select Pills

For date ranges, time periods, preset filters.

```tsx
<div className="flex items-center gap-2">
  {["3 days", "7 days", "14 days", "30 days"].map((period) => (
    <Button
      key={period}
      variant={selected === period ? "default" : "outline"}
      size="sm"
      className="h-8 rounded-full text-xs"
      onClick={() => setSelected(period)}
    >
      {period}
    </Button>
  ))}
</div>
```

**Key rules:**
- `rounded-full` for pill shape
- Active pill uses `variant="default"` (filled), inactive uses `variant="outline"`
- `h-8 text-xs` for compact sizing

---

## Empty State

When there's no data to show.

```tsx
<Card>
  <CardContent className="flex flex-col items-center justify-center py-16 text-center">
    <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-muted">
      <FileText className="h-7 w-7 text-muted-foreground" />
    </div>
    <h3 className="mt-4 font-semibold">No invoices yet</h3>
    <p className="mt-1 max-w-sm text-sm text-muted-foreground">
      Create your first invoice to get started with tracking your revenue.
    </p>
    <Button className="mt-6" size="sm">
      Create Invoice
    </Button>
  </CardContent>
</Card>
```

---

## Sidebar Navigation

Clean left sidebar with grouped sections (Logiqc style).

```tsx
{/* Section label */}
<p className="px-3 text-xs font-medium uppercase tracking-wide text-muted-foreground">
  Registers
</p>

{/* Nav item */}
<a className={cn(
  "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
  isActive
    ? "bg-muted text-foreground"
    : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
)}>
  <Icon className="h-5 w-5" />
  {label}
  {count && (
    <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
      {count}
    </span>
  )}
</a>
```

**Key rules:**
- Active item: `bg-muted text-foreground`
- Inactive: `text-muted-foreground` with hover effect
- Section grouping with uppercase labels
- Notification badge: small `rounded-full` with primary color
- Icons: `h-5 w-5`

### Collapsible Sidebar (preferred pattern)

The sidebar has two states: collapsed (icon-only) and expanded (icon + text). This gives maximum space to data.

```tsx
"use client"
import { cn } from "@/lib/utils"
import { ChevronsLeft, ChevronsRight } from "lucide-react"
import { Button } from "@/components/ui/button"
import { Tooltip, TooltipContent, TooltipTrigger } from "@/components/ui/tooltip"

interface SidebarProps {
  collapsed: boolean
  onToggle: () => void
}

function Sidebar({ collapsed, onToggle }: SidebarProps) {
  return (
    <aside className={cn(
      "fixed inset-y-0 left-0 z-30 flex flex-col border-r bg-card transition-all duration-200",
      collapsed ? "w-16" : "w-64"
    )}>
      {/* Header: Logo + collapse toggle */}
      <div className={cn(
        "flex h-16 items-center border-b px-4",
        collapsed ? "justify-center" : "justify-between"
      )}>
        {collapsed ? (
          <ClairoLogo iconOnly />
        ) : (
          <>
            <ClairoLogo />
            <Button variant="ghost" size="icon" className="h-8 w-8" onClick={onToggle}>
              <ChevronsLeft className="h-4 w-4" />
            </Button>
          </>
        )}
      </div>

      {/* Navigation */}
      <nav className="flex-1 overflow-y-auto p-3 space-y-6">
        {/* Section group */}
        <div className="space-y-1">
          {!collapsed && (
            <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Main
            </p>
          )}
          {navItems.map((item) => (
            <NavItem key={item.href} item={item} collapsed={collapsed} />
          ))}
        </div>

        {/* Another section group — separated by space-y-6 on the parent */}
        <div className="space-y-1">
          {!collapsed && (
            <p className="px-3 pb-1 text-xs font-medium uppercase tracking-wide text-muted-foreground">
              Admin
            </p>
          )}
          {adminItems.map((item) => (
            <NavItem key={item.href} item={item} collapsed={collapsed} />
          ))}
        </div>
      </nav>

      {/* Footer: User + settings */}
      <div className="border-t p-3">
        {collapsed ? (
          <div className="flex justify-center">
            <UserAvatar size="sm" />
          </div>
        ) : (
          <div className="flex items-center gap-3 rounded-lg px-3 py-2">
            <UserAvatar size="sm" />
            <div className="flex-1 min-w-0">
              <p className="truncate text-sm font-medium">{user.name}</p>
              <p className="truncate text-xs text-muted-foreground">{user.email}</p>
            </div>
            <Button variant="ghost" size="icon" className="h-8 w-8 shrink-0">
              <Settings className="h-4 w-4" />
            </Button>
          </div>
        )}
      </div>
    </aside>
  )
}

function NavItem({ item, collapsed }: { item: NavItem; collapsed: boolean }) {
  const isActive = usePathname() === item.href
  const content = (
    <Link
      href={item.href}
      className={cn(
        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
        collapsed && "justify-center px-0",
        isActive
          ? "bg-muted text-foreground"
          : "text-muted-foreground hover:bg-muted/50 hover:text-foreground"
      )}
    >
      <item.icon className="h-5 w-5 shrink-0" />
      {!collapsed && <span>{item.label}</span>}
      {!collapsed && item.count && (
        <span className="ml-auto flex h-5 min-w-5 items-center justify-center rounded-full bg-primary text-[10px] font-medium text-primary-foreground">
          {item.count}
        </span>
      )}
    </Link>
  )

  // In collapsed mode, wrap with tooltip to show label on hover
  if (collapsed) {
    return (
      <Tooltip delayDuration={0}>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right" className="font-medium">
          {item.label}
        </TooltipContent>
      </Tooltip>
    )
  }

  return content
}
```

**Key design rules:**
- Collapsed: `w-16`, icons centered, tooltips on hover for labels
- Expanded: `w-64`, icon + text + optional badge/count
- Transition: `transition-all duration-200` for smooth collapse/expand
- Toggle: `ChevronsLeft`/`ChevronsRight` icon button in header
- Section groups: separated by `space-y-6`, each with optional uppercase label
- User footer: avatar + name/email + settings gear (collapsed = avatar only)
- Main content area adjusts: `pl-16` (collapsed) or `pl-64` (expanded)
- Persist collapsed state in localStorage or Zustand store
