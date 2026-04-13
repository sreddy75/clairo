# Implementation Plan: BAS Transaction Grouping by Xero Reconciliation Status

**Branch**: `057-bas-parked-reconciled` | **Date**: 2026-04-13 | **Spec**: [spec.md](spec.md)

## Summary

Auto-park unreconciled Xero bank transactions in the BAS tax code review flow, and group reconciled transactions in a new collapsible "Reconciled" accordion section. Two new nullable columns on `tax_code_suggestions` (`is_reconciled`, `auto_park_reason`) drive the grouping. Auto-park logic runs during suggestion generation. A new `refresh-reconciliation` endpoint lets accountants re-sync Xero reconciliation status mid-session without a full data re-sync.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, React 18, shadcn/ui (Accordion), TanStack Query
**Storage**: PostgreSQL 16 — 2 new nullable columns + 1 index on `tax_code_suggestions`; no new tables
**Testing**: pytest + pytest-asyncio (backend), TypeScript compiler (frontend)
**Target Platform**: Web (accountant dashboard)
**Performance Goals**: Suggestion list page load unchanged; refresh endpoint < 2s for sessions up to 500 transactions
**Constraints**: Auto-park must never overwrite accountant decisions; `tenant_id` required on all queries; cross-module DB access only via service interfaces
**Scale/Scope**: Affects every BAS session with bank transaction suggestions

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith — no direct cross-module DB access | ✅ PASS | `bas` service calls `xero` service interface for reconciliation map; no direct `XeroBankTransaction` import in `bas` module |
| Repository pattern for all DB access | ✅ PASS | New `apply_reconciliation_refresh()` and `get_bank_transaction_source_ids()` in `BASRepository` |
| `tenant_id` on all queries | ✅ PASS | Both new repository methods include `tenant_id` filter |
| Domain exceptions in service, HTTPException in router | ✅ PASS | `XeroConnectionUnavailableError` raised in service, converted in router |
| Audit events for data modifications | ✅ PASS | `transaction.auto_parked`, `transaction.reconciliation_refreshed`, `transaction.moved_to_reconciled` events |
| No new external infrastructure | ✅ PASS | Reuses existing `XeroBankTransaction.is_reconciled` column; no new services |
| `bulk_create_suggestions` idempotency preserved | ✅ PASS | `ON CONFLICT DO NOTHING` unchanged; auto-park populates fields before insert |
| Pydantic v2 for all schemas | ✅ PASS | New fields added to existing `TaxCodeSuggestionResponse` schema |

## Project Structure

### Documentation (this feature)

```text
specs/057-bas-parked-reconciled/
├── plan.md              ← this file
├── research.md          ← Phase 0 research
├── data-model.md        ← Phase 1 data model
├── quickstart.md        ← developer guide
├── contracts/
│   └── api.md           ← API contract changes
└── tasks.md             ← Phase 2 output (/speckit.tasks command)
```

### Source Code

```text
backend/
├── app/
│   ├── modules/
│   │   └── bas/
│   │       ├── models.py          ← add is_reconciled + auto_park_reason to TaxCodeSuggestion
│   │       ├── schemas.py         ← add fields to TaxCodeSuggestionResponse + Summary
│   │       ├── repository.py      ← add apply_reconciliation_refresh(), get_bank_transaction_source_ids(), extend list_suggestions + get_suggestion_summary
│   │       ├── service.py         ← extend generate_suggestions(); add refresh_reconciliation_status()
│   │       ├── router.py          ← add POST .../refresh-reconciliation endpoint
│   │       └── exceptions.py      ← add XeroConnectionUnavailableError (if absent)
│   └── alembic/
│       └── versions/
│           └── 20260413_add_reconciliation_fields_to_suggestions.py
│
frontend/
└── src/
    ├── lib/
    │   └── bas.ts                 ← extend TaxCodeSuggestion type, add refreshReconciliationStatus()
    └── components/
        └── bas/
            ├── TaxCodeResolutionPanel.tsx  ← add reconciled bucket + AccordionItem, refresh button
            └── TaxCodeSuggestionCard.tsx   ← add "Unreconciled in Xero" badge
```

**Structure Decision**: Modular monolith web application (Option 2). All changes confined to the existing `bas` module (backend) and `components/bas/` (frontend). No new modules, no new services, no new infrastructure.

## Phase 0: Research

✅ Complete — see [research.md](research.md)

**Key findings:**
- `XeroBankTransaction.is_reconciled` already exists in DB — no Xero sync changes needed
- Auto-park via two new nullable columns on `tax_code_suggestions` (no new table)
- Suggestion generation (`generate_suggestions` in `service.py`) is the correct insertion point for auto-park logic
- `bulk_create_suggestions` idempotency (`ON CONFLICT DO NOTHING`) protects existing accountant decisions
- Parked accordion section already exists in `TaxCodeResolutionPanel.tsx:495`
- Cross-module access pattern: `bas` service → `xero` public service interface (not direct model import)

## Phase 1: Design & Contracts

✅ Complete — see [data-model.md](data-model.md), [contracts/api.md](contracts/api.md), [quickstart.md](quickstart.md)

### Data Model Summary

Two nullable columns added to `tax_code_suggestions`:

| Column | Type | Purpose |
|--------|------|---------|
| `is_reconciled` | `Boolean NULL` | `NULL` for invoices/credit notes; `True/False` for bank transactions |
| `auto_park_reason` | `VARCHAR(50) NULL` | `'unreconciled_in_xero'` when system auto-parked; `NULL` otherwise |

One new index: `ix_tax_code_suggestions_session_reconciled` on `(session_id, is_reconciled)`.

### API Summary

| Change | Detail |
|--------|--------|
| `TaxCodeSuggestion` response | +`is_reconciled`, +`auto_park_reason` |
| `TaxCodeSuggestionSummary` response | +`reconciled_count`, +`reconciled_needs_review_count`, +`auto_parked_count` |
| New endpoint | `POST .../refresh-reconciliation` → `{"reclassified_count": N, "newly_reconciled": N, "newly_unreconciled": N}` |

### Frontend Summary

`TaxCodeResolutionPanel.tsx` — 6 buckets (was 5):

| Bucket | Condition |
|--------|-----------|
| `highConfidence` | pending, `is_reconciled !== true`, score ≥ 0.9 |
| `needsReview` | pending, `is_reconciled !== true`, score 0.7–0.9 |
| `manual` | pending, `is_reconciled !== true`, score < 0.7 or null |
| `parked` | dismissed or rejected (all, regardless of `is_reconciled`) |
| `resolved` | approved or overridden, `is_reconciled !== true` |
| `reconciled` *(new)* | `is_reconciled === true` (all statuses) |

`TaxCodeSuggestionCard.tsx` — shows `"Unreconciled in Xero"` badge when `auto_park_reason === 'unreconciled_in_xero'`.

`TaxCodeResolutionPanel.tsx` — "Refresh reconciliation status" button triggers `refreshReconciliationStatus()` and then `loadSuggestions()`.
