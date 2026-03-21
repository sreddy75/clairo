# Quickstart: AI Tax Code Resolution

**Branch**: `046-ai-tax-code-resolution` | **Date**: 2026-03-14

## What This Feature Does

When a BAS is calculated, transactions with missing/unknown tax codes are silently excluded. This feature detects those exclusions, uses AI to suggest the correct tax codes, lets the accountant approve/reject, and recalculates the BAS with the newly mapped transactions.

## Where Things Live

### Backend (all within existing `bas/` module)

```
backend/app/modules/bas/
├── models.py              # ADD: TaxCodeSuggestion, TaxCodeOverride models + enums
├── schemas.py             # ADD: suggestion request/response schemas
├── repository.py          # ADD: suggestion CRUD, override CRUD, excluded item queries
├── tax_code_service.py    # NEW: suggestion engine, resolution logic, conflict detection
├── calculator.py          # MODIFY: capture excluded items in GSTResult
├── service.py             # MODIFY: integrate suggestion summary into BAS summary, approval gate
├── router.py              # ADD: 10 new endpoints under /tax-code-suggestions/
├── exceptions.py          # ADD: SuggestionNotFoundError, InvalidTaxTypeError, etc.
└── a2ui_generator.py      # MODIFY: add exclusion warning to review panel (optional)

backend/app/tasks/
├── bas.py                 # MODIFY: add tax_code_suggestions post-calculation step
└── xero.py                # MODIFY: add "tax_code_suggestions" to PHASE_POST_SYNC_TASKS[2]
```

### Frontend

```
frontend/src/
├── components/bas/
│   ├── BASTab.tsx                  # MODIFY: add exclusion banner, link to resolution panel
│   ├── TaxCodeResolutionPanel.tsx  # NEW: suggestion list with approve/reject/override
│   ├── TaxCodeSuggestionCard.tsx   # NEW: individual suggestion with actions
│   └── TaxCodeBulkActions.tsx      # NEW: bulk approve bar
├── lib/
│   └── bas.ts                      # ADD: API functions for suggestion endpoints
```

## Key Implementation Decisions

1. **Module placement**: Within `bas/`, not a new module — too tightly coupled to BAS calculation.
2. **Override strategy**: Overrides stored in separate `TaxCodeOverride` table, not mutating Xero JSONB — preserves Xero data integrity and enables conflict detection.
3. **Calculator hook**: `GSTResult.excluded_items` collects exclusions during calculation — no separate scan needed.
4. **Suggestion tiers**: Account default (0.95) → client history (0.85-0.95) → tenant history (0.70-0.85) → LLM (0.60-0.80).
5. **Approval gate**: `can_approve` in BAS summary blocked when unresolved suggestions exist.
6. **Idempotency**: Unique constraint on `(session_id, source_type, source_id, line_item_index)` prevents duplicate suggestions.

## Development Order

1. **Models + Migration** — `TaxCodeSuggestion`, `TaxCodeOverride`, new enums
2. **Calculator modification** — capture excluded items in `GSTResult`
3. **Suggestion engine** — 4-tier waterfall classification
4. **Repository + Service** — CRUD for suggestions, resolution logic
5. **Router + Schemas** — API endpoints
6. **BAS service integration** — approval gate, recalculation trigger
7. **Celery task** — post-sync automation
8. **Frontend banner** — exclusion visibility
9. **Frontend resolution panel** — approve/reject/override UI
10. **Conflict detection** — re-sync override comparison

## Testing Strategy

- **Unit tests**: Suggestion engine tiers (each tier independently), confidence scoring, conflict detection logic
- **Integration tests**: Full API endpoint coverage, idempotency, approval gate
- **Calculator tests**: Verify excluded items are captured correctly for all tax type scenarios
- **E2E**: Accountant flow from viewing exclusions → approving → recalculating → approving BAS
