# Research: BAS Transaction Grouping by Xero Reconciliation Status

**Branch**: `057-bas-parked-reconciled` | **Date**: 2026-04-13

---

## Decision 1: `is_reconciled` Already Exists — No Xero Sync Changes Needed

**Decision**: Reuse `XeroBankTransaction.is_reconciled` (Boolean, default `False`) already in the database. No changes to the Xero sync pipeline are required.

**Rationale**: The field was added in migration `20260331_...` and is populated by `transformers.py:391` via `xero_transaction.get("IsReconciled", False)` on every sync. An index already exists on `(xero_bank_account_id, is_reconciled, transaction_date)` for efficient filtering.

**Alternatives considered**: Fetching `IsReconciled` live from Xero on each BAS page load — rejected because it adds latency and Xero rate limit pressure. The synced value is sufficient for this use case.

---

## Decision 2: Add `is_reconciled` + `auto_park_reason` to `TaxCodeSuggestion`

**Decision**: Add two nullable columns to the `tax_code_suggestions` table:
- `is_reconciled: Boolean | None` — `None` for non-bank-transaction sources (invoices, credit notes); `True/False` for bank transactions.
- `auto_park_reason: String(50) | None` — set to `"unreconciled_in_xero"` when auto-parked; `None` for manually parked or non-auto-parked suggestions.

**Rationale**: Embedding `is_reconciled` on the suggestion row avoids a live join to `xero_bank_transactions` on every suggestion list query. The `auto_park_reason` distinguishes auto-parked from manually parked at the API level without inspecting `note_text`.

**Alternatives considered**:
- Live join to `XeroBankTransaction` on each `list_suggestions` call — rejected because it adds a cross-module join and slows the already-expensive suggestion list query.
- Storing reconciliation status only in a separate table — rejected as over-engineering for a two-column addition.

---

## Decision 3: Auto-Park Logic Lives in the Suggestion Generation Service

**Decision**: When `generate_suggestions` creates `TaxCodeSuggestion` rows for bank transactions, it joins to `XeroBankTransaction` to read `is_reconciled` and:
- Sets `is_reconciled` on the suggestion row.
- If `is_reconciled = False`, sets `status = "dismissed"` and `auto_park_reason = "unreconciled_in_xero"` instead of `"pending"`.

The existing `bulk_create_suggestions` uses `INSERT … ON CONFLICT DO NOTHING`, so it is idempotent — re-running generation does not overwrite accountant decisions (the unique constraint blocks re-insertion of already-existing rows).

**Rationale**: The generation service already has access to the DB session and the connection context needed to query `XeroBankTransaction`. This keeps auto-park logic server-side and deterministic.

**Alternatives considered**:
- A separate Celery task that runs after generation to auto-park — rejected as unnecessary complexity for a synchronous pre-processing step.
- Auto-parking in the router at request time — rejected as business logic belongs in the service layer (Constitution §I).

---

## Decision 4: Reconciliation Refresh = Targeted Re-Query + Selective Re-Park

**Decision**: New endpoint `POST .../tax-code-suggestions/refresh-reconciliation`:
1. Queries `XeroBankTransaction.is_reconciled` for all `source_id` values referenced by bank-transaction suggestions in the session.
2. Updates `is_reconciled` on each affected `TaxCodeSuggestion` row.
3. For suggestions where `is_reconciled` changed from `False → True` **and** `auto_park_reason = "unreconciled_in_xero"` (i.e., auto-parked, not manually parked): sets `status = "pending"` and clears `auto_park_reason`.
4. For suggestions where `is_reconciled` changed from `True → False` **and** `status = "pending"`: auto-parks them.
5. Logs `transaction.reconciliation_refreshed` audit event.

**Rationale**: Refresh only touches suggestions that have not been acted on by the accountant (auto_park_reason check). Manually dismissed items are never reclassified.

**Alternatives considered**:
- Full re-sync of Xero data on refresh — rejected as too heavy (calls multiple Xero API endpoints). The refresh only re-reads `IsReconciled` for the specific transaction IDs in the session.
- Triggering a Celery task for refresh — rejected as the operation is fast (targeted query by `source_id` list) and the user expects immediate feedback.

---

## Decision 5: Frontend — New "Reconciled" Accordion Section, Not a Separate Component

**Decision**: Extend `TaxCodeResolutionPanel.tsx` with a new `AccordionItem value="reconciled"` section. The `reconciled` bucket = suggestions where `is_reconciled === true` (regardless of status). This section:
- Is **not** in the default open set (added to the current `['high', 'review', 'manual', 'resolved']` list).
- Shows `Reconciled ({count})` in the trigger, plus `— {n} need review` if any reconciled suggestion has `status === 'pending'`.
- The existing `SuggestionTable` is reused with a `readOnly` prop for approved/overridden reconciled items.

The "Parked" section already exists (line 495 in `TaxCodeResolutionPanel.tsx`). It is extended to show auto-parked items with a label badge ("Unreconciled in Xero") using the `auto_park_reason` field.

**Rationale**: Reusing `AccordionItem` and `SuggestionTable` is the minimum-code path. No new component is needed.

**Alternatives considered**:
- A separate full-page component for reconciled items — rejected as overkill for what is essentially a collapsible table section.
- Separate accordion for the entire panel — rejected as it breaks the existing UX flow accountants are familiar with.

---

## Decision 6: Non-Bank Transactions Excluded from Auto-Park

**Decision**: `is_reconciled = None` for invoices and credit notes. Auto-park logic does not apply to them. They flow through the existing confidence-based pending buckets unchanged.

**Rationale**: Xero's `IsReconciled` field applies to `BankTransaction` objects only. Invoices and credit notes have a different lifecycle (approved/voided, not reconciled). The spec assumption is confirmed by the writeback service which checks `doc.get("IsReconciled")` only on bank transactions.

---

## Resolved Unknowns

| Unknown | Resolution |
|---------|------------|
| Is `XeroBankTransaction.is_reconciled` already synced? | Yes — present since migration `20260331_...`, populated by transformer at `transformers.py:391` |
| Does suggestion generation already have DB access to join to Xero tables? | Yes — `generate_suggestions` uses the same `AsyncSession`; both modules are in the same process (modular monolith) |
| Does `bulk_create_suggestions` overwrite existing rows? | No — uses `INSERT … ON CONFLICT DO NOTHING`; existing rows are skipped, protecting accountant decisions |
| Is the "Parked" section already in the frontend? | Yes — `TaxCodeResolutionPanel.tsx:495`, triggered by `status === 'dismissed' || 'rejected'` |
| Does the refresh need a Celery task? | No — targeted query by `source_id` list is fast enough for synchronous response |
| Does the writeback service block on reconciled transactions? | Yes — `writeback_service.py:618` raises `XeroDocumentNotEditableError` if reconciled; auto-parked unreconciled items can still be written back after approval |
