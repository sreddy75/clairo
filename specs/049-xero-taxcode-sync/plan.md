# Implementation Plan: Xero Tax Code Write-Back + Bank Transaction Line Items & Splits

**Branch**: `049-xero-taxcode-sync` | **Date**: 2026-04-07 | **Spec**: [spec.md](spec.md)

## Summary

Writes approved tax code overrides back to Xero invoices, bank transactions, and credit notes via the Xero REST API. Extends the client portal with mandatory "I don't know" descriptions, all-questions gate, multi-round send-back, and per-transaction agent notes. Adds UI support for bank transaction line items: viewing per-line-item tax codes on existing splits, and creating/editing new splits directly in Clairo before sync.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript 5.x / Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Pydantic v2, Celery + Redis, anthropic SDK, Xero OAuth2 API, React 18, shadcn/ui, TanStack Query, Zustand
**Storage**: PostgreSQL 16 — 4 new tables, 2 modified tables (original scope); +4 columns on `tax_code_overrides` (split scope)
**Testing**: pytest + pytest-asyncio (backend), no frontend unit tests required
**Target Platform**: Linux server (backend), Vercel (frontend)
**Performance Goals**: Sync ≤50 items within 2 minutes end-to-end (SC-001)
**Constraints**: Xero rate limit 60 calls/minute; bank transaction splits balance must equal transaction total
**Scale/Scope**: Per-BAS-session writeback, typical 10–50 documents per session

## Constitution Check

| Gate | Status | Notes |
|------|--------|-------|
| Modular monolith boundaries | ✅ Pass | Writeback in `integrations/xero`; classification extensions in `bas`; no cross-module direct DB access |
| Repository pattern | ✅ Pass | All DB access via repositories; services call repos only |
| No `HTTPException` in service layer | ✅ Pass | Domain exceptions in `core/exceptions.py`, converted in router |
| `tenant_id` on all queries | ✅ Pass | All new tables have `tenant_id`; all queries filter by it |
| Celery tasks idempotent | ✅ Pass | Task checks `XeroWritebackItem.status != success` before processing |
| shadcn/ui components only | ✅ Pass | All new UI uses Badge, Button, Card, Table, Accordion from shadcn |
| CSS variable tokens | ✅ Pass | No hardcoded hex/hsl values |

## Project Structure

### Documentation (this feature)

```text
specs/049-xero-taxcode-sync/
├── plan.md              # This file
├── research.md          # Phase 0 output (decisions 1-17)
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/           # Phase 1 output
└── tasks.md             # Phase 2 output (/speckit.tasks)
```

### Source Code

```text
backend/
├── app/
│   ├── modules/
│   │   ├── bas/
│   │   │   ├── models.py                        # TaxCodeOverride: +writeback_status, +line_amount, +line_description, +line_account_code, +is_new_split
│   │   │   ├── tax_code_service.py              # approve/override/bulk_approve already create overrides; add split CRUD methods
│   │   │   ├── classification_service.py        # extend: send_items_back, get_classification_thread
│   │   │   ├── classification_models.py         # ClassificationRequest: +parent_request_id, +round_number; new: AgentTransactionNote, ClientClassificationRound
│   │   │   ├── repository.py                    # add: get_splits_for_transaction, create_split_override, update_split_override, delete_split_override
│   │   │   ├── schemas.py                       # TaxCodeOverrideSchema: +split fields; new: SplitCreateRequest, SplitUpdateRequest
│   │   │   └── router.py                        # new: POST/PATCH/DELETE /splits endpoints; GET /tax-rates already exists
│   │   └── integrations/xero/
│   │       ├── writeback_models.py              # XeroWritebackJob, XeroWritebackItem (new file)
│   │       ├── writeback_service.py             # XeroWritebackService; apply_overrides_to_line_items extended
│   │       └── router.py                        # POST /writeback, GET /writeback/jobs/{job_id}, POST /writeback/jobs/{job_id}/retry
│   └── tasks/
│       └── xero_writeback.py                    # process_writeback_job Celery task; handle is_new_split in payload reconstruction
│
├── alembic/versions/
│   ├── xxxx_add_xero_writeback_tables.py
│   ├── xxxx_add_tax_code_override_writeback_status.py
│   ├── xxxx_extend_classification_requests_for_sendback.py
│   ├── xxxx_add_agent_transaction_notes.py
│   ├── xxxx_add_client_classification_rounds.py
│   └── xxxx_add_tax_code_override_split_columns.py
│
└── tests/
    └── unit/
        ├── tasks/
        │   └── test_xero_writeback.py           # extend: new split-mode tests for apply_overrides_to_line_items
        └── modules/bas/
            └── test_split_service.py            # balance validation, split CRUD

frontend/
└── src/
    ├── components/
    │   └── bas/
    │       ├── TaxCodeResolutionPanel.tsx        # group suggestions by source_id; TransactionGroup component
    │       ├── TransactionLineItemGroup.tsx      # new: collapsible parent row with child line item rows
    │       ├── SplitCreationForm.tsx             # new: inline form for add/edit/remove splits
    │       ├── SplitBalanceIndicator.tsx         # new: running total vs transaction amount
    │       └── TaxCodeSuggestionCard.tsx         # minor: accept is_new_split / pending badge prop
    └── lib/
        └── bas.ts                               # add: createSplit, updateSplit, deleteSplit, getSplits API functions
```

## Implementation Phases

### Phase A — Backend: DB Migration + Model Extension (split columns)

1. Alembic migration: add `line_amount`, `line_description`, `line_account_code`, `is_new_split` to `tax_code_overrides`
2. Update `TaxCodeOverride` SQLAlchemy model in `bas/models.py`
3. Update `TaxCodeOverrideSchema` in `bas/schemas.py` to include new fields

### Phase B — Backend: Split CRUD Service + Endpoints

1. Add split methods to `TaxCodeService`: `create_split_override`, `update_split_override`, `delete_split_override`, `get_splits_for_transaction`
2. Balance validation helper: `_validate_split_balance(source_id, tenant_id, db)` — raises `422` if unbalanced
3. Add three endpoints to `bas/router.py`:
   - `POST /sessions/{session_id}/bank-transactions/{source_id}/splits`
   - `PATCH /sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}`
   - `DELETE /sessions/{session_id}/bank-transactions/{source_id}/splits/{override_id}`

### Phase C — Backend: `apply_overrides_to_line_items` Extension

1. Extend function to handle `is_new_split=True` (insert mode)
2. Add `validate_balance` + `expected_total` parameters
3. Patch `line_amount`, `line_description`, `line_account_code` fields when non-null
4. Update Celery task to call with `validate_balance=True` for documents that have any `is_new_split` overrides
5. Update unit tests in `test_xero_writeback.py`

### Phase D — Frontend: Group Suggestions by source_id

1. Compute `transactionGroups: Map<string, TaxCodeSuggestion[]>` in `TaxCodeResolutionPanel`
2. Build `TransactionLineItemGroup` component: collapsible parent + child `TaxCodeSuggestionCard` rows
3. Single-item groups → render existing `TaxCodeSuggestionCard` unchanged (no regression)
4. Multi-item groups → render parent row (date, total, contact) + expanded child rows

### Phase E — Frontend: Split Creation UI

1. Add `SplitCreationForm` component: inline form attached to single-line bank transaction rows
2. Add `SplitBalanceIndicator`: shows running total vs. transaction amount, red when unbalanced
3. Connect to `createSplit` / `updateSplit` / `deleteSplit` API functions in `bas.ts`
4. Show "Pending" badge on unsynced agent-defined splits
5. Aggregate Xero status on parent `TransactionLineItemGroup` row

## Complexity Tracking

No constitution violations. All new work fits the existing modular monolith pattern.
