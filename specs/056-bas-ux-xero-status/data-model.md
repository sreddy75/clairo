# Data Model: 056-bas-ux-xero-status

## Schema Changes

### Modified Table: `tax_code_suggestions`

Add 3 new columns to the existing table:

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| `note_text` | TEXT | Yes | NULL | Free-text note (max 2,000 chars, enforced in app layer) |
| `note_updated_by` | UUID (FK → practice_users.id) | Yes | NULL | Last user who edited the note |
| `note_updated_at` | TIMESTAMPTZ | Yes | NULL | When note was last edited |

### Existing Column Behavior Changes

| Column | Change | Detail |
|--------|--------|--------|
| `dismissal_reason` | Soft-deprecated | No longer written to by new code. Existing values preserved. Display layer reads `note_text` first, falls back to `dismissal_reason` for old records. |
| `status` | No schema change | `rejected` value retained in DB. Display layer maps `rejected` → "Dismissed". New dismissals write `dismissed`. |

### Migration

```sql
-- Add note columns to tax_code_suggestions
ALTER TABLE tax_code_suggestions
    ADD COLUMN note_text TEXT,
    ADD COLUMN note_updated_by UUID REFERENCES practice_users(id) ON DELETE SET NULL,
    ADD COLUMN note_updated_at TIMESTAMPTZ;

-- Migrate existing dismissal_reason values to note_text for dismissed suggestions
UPDATE tax_code_suggestions
SET note_text = dismissal_reason,
    note_updated_at = resolved_at
WHERE dismissal_reason IS NOT NULL AND note_text IS NULL;

-- Index for efficient "has note" filtering
CREATE INDEX ix_tax_code_suggestions_has_note
ON tax_code_suggestions (session_id)
WHERE note_text IS NOT NULL;
```

### No New Tables

The 1:1 relationship between suggestion and note is handled by columns on `tax_code_suggestions`. No `suggestion_notes` table needed.

## Entity Relationships

```
TaxCodeSuggestion (modified)
├── note_text: TEXT (nullable) — free-text note, replaces dismissal_reason for new records
├── note_updated_by → PracticeUser (nullable) — who last edited the note
├── note_updated_at: TIMESTAMPTZ (nullable) — when note was last edited
└── [existing columns unchanged]
```

## State Transitions

### Suggestion Status (unchanged schema, changed behavior)

```
pending → approved (Approve action)
pending → overridden (Override action)
pending → dismissed (Park it action — formerly also had "rejected")
dismissed → approved (Approve from Parked section)
dismissed → pending (Back to Manual / unpark from Parked section)

Note: "rejected" still exists in DB for old records.
       New reject API calls → internally create "dismissed" status.
       Display layer maps both "rejected" and "dismissed" to "Parked".
       No `note_xero_sync_status` column — Xero note sync is fire-and-forget with no persistent status.
```

## Xero BAS Cross-Check (Transient Data)

No persistence needed. The cross-check data is fetched from Xero on each BAS tab load and displayed in the frontend. Structure:

```typescript
interface XeroBASCrossCheck {
  found: boolean;              // Whether Xero has a BAS report for this period
  xero_1a: number | null;     // GST on sales from Xero
  xero_1b: number | null;     // GST on purchases from Xero
  xero_net_gst: number | null; // Net GST from Xero (1A - 1B)
  period_label: string;       // e.g., "Q3 2025-26"
  fetched_at: string;         // ISO timestamp of when data was fetched
}
```
