# Design Tokens

## Color Palette

### Backgrounds
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--background` | Warm off-white `40 20% 97%` | Deep charcoal `222 50% 6%` | Page background |
| `--card` | Pure white `0 0% 100%` | Dark surface `224 40% 10%` | Cards, panels |
| `--muted` | Light warm gray `40 15% 94%` | Dark muted `220 30% 14%` | Secondary backgrounds, hover states |
| `--accent` | Light warm gray `40 15% 94%` | Dark accent `220 30% 14%` | Interactive element backgrounds |

### Text
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--foreground` | Near-black `222 47% 11%` | Off-white `210 40% 98%` | Primary text, headings, numbers |
| `--muted-foreground` | Medium gray `220 10% 46%` | Light gray `220 15% 60%` | Labels, captions, secondary text |
| `--card-foreground` | Same as foreground | Same as dark foreground | Text inside cards |

### Interactive
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--primary` | Coral `12 80% 55%` | Coral bright `12 80% 60%` | Primary CTA buttons |
| `--primary-foreground` | White `0 0% 100%` | White `0 0% 100%` | Text on primary buttons |
| `--secondary` | Light warm gray `40 15% 94%` | Dark secondary `220 30% 18%` | Secondary buttons |
| `--ring` | Coral `12 80% 55%` | Coral `12 80% 60%` | Focus rings |

### Status (semantic — use these, not raw Tailwind colors)
| Name | Token/Class | Light | Dark | When |
|------|-------------|-------|------|------|
| Success | `--status-success` | `emerald-600` | `emerald-400` | Completed, paid, connected, healthy |
| Warning | `--status-warning` | `amber-600` | `amber-400` | Due soon, attention needed, review |
| Danger | `--status-danger` | `red-600` | `red-400` | Overdue, failed, disconnected, urgent |
| Info | `--status-info` | `blue-600` | `blue-400` | In progress, pending, informational |
| Neutral | `--status-neutral` | `stone-500` | `stone-400` | Draft, inactive, N/A |

**Status usage pattern:**
```tsx
// Status dot indicator (like Logiqc reference)
<span className="inline-flex items-center gap-1.5 text-sm">
  <span className={cn("h-2 w-2 rounded-full", statusConfig[status].dot)} />
  {statusConfig[status].label}
</span>

// Status badge
<Badge variant="outline" className={cn("text-xs", statusConfig[status].badge)}>
  {statusConfig[status].label}
</Badge>
```

### Chart Colors
| Token | Value | Usage |
|-------|-------|-------|
| `--chart-1` | Coral (primary CTA color) | Primary data series |
| `--chart-2` | Teal/emerald | Secondary data series |
| `--chart-3` | Amber | Tertiary |
| `--chart-4` | Soft purple | Quaternary |
| `--chart-5` | Slate | Quinary |

Charts should use **maximum 2-3 colors**. If >3 series, use shades of 1-2 base colors.

### Borders & Inputs
| Token | Light | Dark | Usage |
|-------|-------|------|-------|
| `--border` | `220 15% 90%` | `220 20% 18%` | Card borders, dividers |
| `--input` | `220 15% 90%` | `220 20% 18%` | Form input borders |

Borders should be **subtle**. Prefer separation through whitespace and background difference over visible borders.

---

## Typography

### Font Families
- **Headings**: Sora (`--font-heading`) — geometric, modern, clean
- **Body**: Plus Jakarta Sans (`--font-sans`) — warm, readable, professional

### Type Scale — Professional Density (strict — no deviation)
| Role | Class | Weight | Usage |
|------|-------|--------|-------|
| Page title | `text-xl font-semibold tracking-tight` | 600 | One per page, top-left |
| Section heading | `text-lg font-semibold` | 600 | Card titles, section labels |
| Section label | `text-xs font-medium uppercase tracking-wide text-muted-foreground` | 500 | "MY DETAILS", "INVOICE DETAILS" style labels |
| Body | `text-sm` | 400 | Default text, descriptions, table cells |
| Caption | `text-xs text-muted-foreground` | 400 | Helper text, timestamps, metadata |
| Hero number (stat cards) | `text-2xl font-bold tracking-tight tabular-nums` | 700 | KPI values, stat card numbers — **DATA IS THE HERO** |
| Hero number (BAS total) | `text-3xl font-bold tracking-tight tabular-nums` | 700 | Single featured total — BAS payable only |
| BAS field values | `text-lg font-bold tabular-nums` | 700 | G1, G2, W1 etc. field card values |
| Table header | `text-xs font-medium text-muted-foreground` | 500 | Column headers |
| Label | `text-xs font-medium text-muted-foreground` | 500 | Form field labels |

### Number Formatting
Numbers are the most important visual element. They MUST be:
- **Bold with `tabular-nums`** — ALWAYS. No exceptions for any numerical display.
- **`text-2xl`** in stat cards (not `text-3xl` — professional density)
- **Right-aligned** in tables
- **Formatted** with `formatCurrency()`, `formatPercentage()` from `@/lib/formatters` — never raw numbers, never local formatters
- **Monospace digits** use `tabular-nums` for aligned columns in tables AND stat cards

```tsx
// Stat card hero number
<span className="text-2xl font-bold tracking-tight tabular-nums">
  {formatCurrency(amount)}
</span>

// Table cell
<td className="text-right tabular-nums font-medium">
  {formatCurrency(amount)}
</td>
```

---

## Spacing

### Layout Constants — Professional Density
| Element | Value | Class |
|---------|-------|-------|
| Sidebar width | 256px | `w-64` |
| Header height | 56px | `h-14` |
| Content padding | 20px | `p-5` |
| Stat card padding | 16px | `p-4` |
| Form card padding | 24px | `p-6` |
| Stat card grid gap | 12px | `gap-3` |
| Page section gap | 20px | `space-y-5` |
| Between label and content | 16px | `gap-4` |
| Table header height | 36px | `h-9` (shadcn TableHead) |
| Table cell padding | 6px vert, 8px horiz | `px-2 py-1.5` (shadcn TableCell) |
| Manual table header | — | `px-4 py-2 text-xs font-medium` |
| Manual table cell | — | `px-4 py-2.5 text-sm` |

### Spacing Philosophy
- Use `gap-3` between stat cards in a grid
- Use `gap-4` between form cards or larger content cards
- Use `space-y-5` between major page sections
- Use `gap-4` within card content
- Use `gap-1.5` between label and value in a form field
- **Data density over decoration.** Accountants need to see more data per screen. Tight but not cramped.

---

## Border Radius
| Token | Value | Usage |
|-------|-------|-------|
| `--radius` (lg) | `0.75rem` (12px) | Cards, dialogs, large containers |
| md | `0.5rem` (8px) | Buttons, inputs, badges |
| sm | `0.375rem` (6px) | Small elements, chips |
| full | `9999px` | Status dots, avatars, pills |

---

## Shadows
Keep shadows **minimal**. Separation comes from background color difference, not shadow depth.

| Level | Class | Usage |
|-------|-------|-------|
| None | `shadow-none` | Default for most cards (use border instead) |
| Subtle | `shadow-sm` | Cards that need slight lift |
| Elevated | `shadow-md` | Dropdowns, popovers, floating elements |
| Modal | `shadow-lg` | Dialogs, modals |

---

## Dark Mode Conventions

- Light mode background: warm off-white. Dark mode: deep charcoal (not pure black).
- Light: `gray-*` NOT used. Use warm tones. Dark: `stone-*` palette for all grays.
- Colored backgrounds in dark mode: use `/10` or `/20` opacity (e.g., `bg-emerald-500/10`)
- Status dot colors stay the same in both modes, but text color adapts
- Cards in dark mode: slightly lighter than background (`--card` vs `--background`)
