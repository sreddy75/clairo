# Research: 056-bas-ux-xero-status

## R1: Note Storage Strategy — New Table vs Column on TaxCodeSuggestion

**Decision**: Add columns directly to `tax_code_suggestions` table (not a separate table).

**Rationale**: The spec says "one note per suggestion (upsert model)." This is a 1:1 relationship. Adding `note_text`, `note_updated_by`, `note_updated_at`, and `note_xero_sync_status` columns directly to `TaxCodeSuggestion` avoids a JOIN on every suggestion list query. The existing `dismissal_reason` column (Text, nullable) already stores a reason on dismiss — the note field replaces it conceptually, but we keep `dismissal_reason` as-is for backward compat and add new `note_text` alongside it. During dismiss, the service writes to `note_text` (the new unified field) instead of `dismissal_reason`.

**Alternatives considered**:
- Separate `suggestion_notes` table: Rejected — adds unnecessary JOIN complexity for a 1:1 relationship. Would only be justified if we needed note history (we use audit trail instead).
- Repurpose `dismissal_reason` directly: Rejected — would break existing data semantics. Better to add new columns and migrate the dismiss flow to use them.

## R2: Reject→Dismiss Mapping Strategy

**Decision**: Backend `/reject` endpoint internally calls `dismiss_suggestion` service method. Keep `REJECTED` enum in `TaxCodeSuggestionStatus` for database backward compat. Frontend maps both `rejected` and `dismissed` statuses to display as "Dismissed."

**Rationale**: No data migration needed. Existing rejected records stay as-is in the DB. The display layer handles the mapping. The `/reject` API endpoint remains functional but is deprecated — it calls the same dismiss logic internally.

**Alternatives considered**:
- Data migration to change all `rejected` → `dismissed`: Rejected — unnecessary risk for a display-only change. Audit trail integrity is better preserved by keeping original values.
- Remove `/reject` endpoint entirely: Rejected — could break any in-flight API calls during deployment window.

## R3: Xero History & Notes API Integration

**Decision**: Add `add_history_note()` method to `XeroClient`. Sync is fire-and-forget — no persistent status tracking, no retry endpoint. The call is made inline when saving the note; success or failure is logged but not stored on the suggestion row.

**Rationale**: The Xero History & Notes API is a simple `PUT /{EntityType}/{EntityID}/History` with a `{"HistoryRecords": [{"Details": "..."}]}` body. It's append-only (no edit/delete). Response time is typically <500ms. Tracking sync status (pending/synced/failed) and offering a retry button adds significant complexity (extra DB column, state machine, retry endpoint, frontend status UI) for a feature that is auxiliary. Fire-and-forget keeps the implementation simple — if the call fails, it is logged for debugging but the user is not burdened with retry workflows.

**Endpoint pattern**:
- Bank transactions: `PUT /BankTransactions/{BankTransactionID}/History`
- Invoices: `PUT /Invoices/{InvoiceID}/History`
- Credit notes: `PUT /CreditNotes/{CreditNoteID}/History`

**Key constraint**: `Details` field max 450 characters. Truncation with "..." suffix if Clairo note exceeds this.

**Alternatives considered**:
- Persistent status tracking with retry: Rejected — adds a DB column (`note_xero_sync_status`), a state machine (pending/synced/failed), a retry endpoint, and frontend status UI for a feature that rarely fails and is not critical.
- Celery background job: Rejected — overkill for a single fast PUT call. Would require job model, status polling, and more frontend complexity.
- Batch sync (collect notes, sync periodically): Rejected — adds unnecessary delay for a simple inline call.

## R4: Xero BAS Report Cross-Check

**Decision**: Add `get_bas_report()` method to `XeroClient` following existing report pattern. Fetch on BAS session detail load (not session list). Parse BAS label amounts (1A, 1B) from the generic report row structure.

**Rationale**: The `GET /Reports/BAS` endpoint returns a generic Xero report structure with rows/cells. The BAS labels (1A, 1B, etc.) are in `Row.Cells[0].Value` and the amounts in `Row.Cells[1].Value`. This matches the pattern used for other reports in `client.py`. The fetch happens when a session detail is opened (alongside existing calculation/variance fetches), not on session list load, to avoid unnecessary API calls.

**Report structure** (from Xero):
```json
{
  "Reports": [{
    "ReportName": "BAS",
    "Rows": [
      {"RowType": "Header", "Cells": [{"Value": "Label"}, {"Value": "Amount"}]},
      {"RowType": "Row", "Cells": [{"Value": "1A"}, {"Value": "1234.56"}]},
      {"RowType": "Row", "Cells": [{"Value": "1B"}, {"Value": "567.89"}]}
    ]
  }]
}
```

**Alternatives considered**:
- Cache BAS report data in DB: Rejected — adds storage complexity for data that should always be fresh from Xero.
- Fetch on session list load: Rejected — would multiply API calls (one per session) and slow down the list page.

## R5: Frontend Note Editor UX

**Decision**: Popover-based inline editor triggered by a note icon on each suggestion row. Uses shadcn/ui `Popover` + `Textarea` + `Button`. Shows character counter (2,000 max). Optional "Sync to Xero" checkbox visible only when Xero connection is active and source type supports History & Notes.

**Rationale**: A popover keeps the user in context (no modal or page navigation). It's consistent with the existing inline action patterns in the suggestion table (approve/dismiss buttons are already inline). The textarea with character counter is a standard pattern.

**Alternatives considered**:
- Full modal: Rejected — too heavy for a quick note. Would interrupt the review flow.
- Expandable row section: Rejected — would disrupt table layout and require significant CSS changes.
- Tooltip-only display: Rejected — too constrained for editing. Tooltips are read-only.
