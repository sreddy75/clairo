# Implementation Plan: AI Tax Code Resolution for BAS Preparation

**Branch**: `046-ai-tax-code-resolution` | **Date**: 2026-03-14 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/046-ai-tax-code-resolution/spec.md`

## Summary

BAS calculations silently exclude transactions with missing/unknown tax codes, producing understated BAS figures. This feature adds: (1) detection of excluded transactions during BAS calculation, (2) AI-powered tax code suggestion using a 4-tier confidence waterfall (account defaults → client history → tenant history → LLM), (3) accountant review/approve/reject/override workflow, (4) automatic BAS recalculation after approvals, and (5) re-sync conflict detection for locally applied overrides.

All new code lives within the existing `bas/` module. Overrides are stored in a separate table (not mutating Xero JSONB) to preserve data integrity and enable conflict detection.

## Technical Context

**Language/Version**: Python 3.12+ (backend), TypeScript/Next.js 14 (frontend)
**Primary Dependencies**: FastAPI, SQLAlchemy 2.0, Celery, Anthropic SDK (Claude Sonnet for LLM tier), React 18 + shadcn/ui
**Storage**: PostgreSQL 16 (2 new tables: `tax_code_suggestions`, `tax_code_overrides`)
**Testing**: pytest + pytest-asyncio (backend), Playwright (E2E)
**Target Platform**: Web application (Linux server + Vercel frontend)
**Project Type**: Web (modular monolith backend + Next.js frontend)
**Performance Goals**: Suggestion generation < 5s for 50 items (tiers 1-3); LLM tier < 10s per item; BAS recalculation < 3s
**Constraints**: All queries tenant-scoped via RLS; audit trail for ATO compliance; human-in-the-loop (no auto-apply)
**Scale/Scope**: Typical quarterly BAS has 0-100 excluded transactions; up to 500 in edge cases

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Gate | Status | Notes |
|------|--------|-------|
| Architecture: Modular Monolith | PASS | Adding to existing `bas/` module — follows modular monolith pattern |
| Module Boundaries | PASS | New service (`tax_code_service.py`) within `bas/`; reads Xero data via Xero module's repository (not cross-module internals — repositories are shared DB access) |
| Repository Pattern | PASS | All DB access via repository methods with `flush()` |
| Multi-Tenancy | PASS | `tenant_id` on both new tables, indexed, RLS-scoped |
| Testing Strategy | PASS | Unit tests for suggestion engine, integration tests for endpoints, E2E for workflow |
| Code Quality Standards | PASS | Type hints, Pydantic schemas, domain exceptions extending `DomainError` |
| API Design Standards | PASS | RESTful endpoints under existing BAS prefix |
| Auditing & Compliance | PASS | New `BASAuditEventType` values; all resolutions logged via existing `BASAuditLog` |
| Human-in-the-Loop | PASS | AI suggests, accountant approves — no auto-apply |
| Layer Compliance | PASS | Layer 1 (Core BAS) + Layer 3 (AI) for LLM tier only |

**Post-Phase 1 re-check**: All gates still pass. No new violations introduced by the data model or API design.

## Project Structure

### Documentation (this feature)

```text
specs/046-ai-tax-code-resolution/
├── spec.md              # Feature specification
├── plan.md              # This file
├── research.md          # Phase 0 research decisions
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer quickstart
├── contracts/
│   └── api.md           # API endpoint contracts
├── checklists/
│   └── requirements.md  # Spec quality checklist
└── tasks.md             # Phase 2 task list (created by /speckit.tasks)
```

### Source Code (repository root)

```text
backend/app/modules/bas/
├── models.py                  # MODIFY: add TaxCodeSuggestion, TaxCodeOverride, enums
├── schemas.py                 # MODIFY: add suggestion request/response schemas
├── repository.py              # MODIFY: add suggestion + override CRUD methods
├── tax_code_service.py        # NEW: suggestion engine, resolution, conflict detection
├── calculator.py              # MODIFY: capture excluded items in GSTResult
├── service.py                 # MODIFY: integrate approval gate, recalc trigger
├── router.py                  # MODIFY: add 10 tax-code-suggestion endpoints
└── exceptions.py              # MODIFY: add SuggestionNotFoundError, etc.

backend/app/tasks/
├── bas.py                     # MODIFY: add suggestion generation post-calculation
└── xero.py                    # MODIFY: add conflict detection post-sync

backend/alembic/versions/
└── 046_add_tax_code_resolution.py  # NEW: migration for 2 tables

backend/tests/
├── unit/modules/bas/
│   ├── test_tax_code_service.py    # NEW: suggestion engine unit tests
│   └── test_calculator_excluded.py # NEW: excluded item capture tests
└── integration/api/
    └── test_tax_code_suggestions.py # NEW: endpoint integration tests

frontend/src/
├── components/bas/
│   ├── BASTab.tsx                   # MODIFY: add exclusion banner
│   ├── TaxCodeResolutionPanel.tsx   # NEW: suggestion list with actions
│   ├── TaxCodeSuggestionCard.tsx    # NEW: individual suggestion card
│   └── TaxCodeBulkActions.tsx       # NEW: bulk approve bar
└── lib/
    └── bas.ts                       # MODIFY: add suggestion API functions
```

**Structure Decision**: Extending the existing `bas/` module rather than creating a new module. The feature is tightly coupled to BAS calculation, uses the same `TAX_TYPE_MAPPING`, and triggers BAS recalculation. A separate module would require cross-module imports of BAS internals, violating module boundaries.

## Key Design Decisions

### D1: Override Storage Strategy

**Decision**: Store overrides in `TaxCodeOverride` table, apply during BAS calculation by overlaying on Xero JSONB data.

**How it works**:
1. When accountant approves/overrides, create a `TaxCodeOverride` record
2. When BAS calculator processes line items, check for active overrides first
3. If an override exists for `(connection_id, source_type, source_id, line_item_index)`, use the override's `tax_type` instead of the JSONB value
4. The Xero JSONB is never mutated — Xero data stays pristine

**Why not mutate JSONB**: The Xero upsert (`ON CONFLICT DO UPDATE`) overwrites the entire `line_items` column on re-sync. Any local mutations would be silently lost. The override table provides persistence across re-syncs and enables conflict detection.

### D2: Suggestion Engine Architecture

```
detect_excluded_items(session)
  │
  ├─ For each excluded line item:
  │   │
  │   ├─ Tier 1: lookup account_code → XeroAccount.default_tax_type
  │   │   If valid (not excluded): confidence 0.95, done
  │   │
  │   ├─ Tier 2: query same connection's historical tax_types for this account_code
  │   │   If ≥90% match single type: confidence 0.85-0.95 (scaled by %), done
  │   │
  │   ├─ Tier 3: query all tenant connections' historical tax_types for this account_code
  │   │   If ≥85% match: confidence 0.70-0.85, done
  │   │
  │   └─ Tier 4: batch remaining items → Claude classification
  │       confidence 0.60-0.80 based on LLM confidence signal
  │
  └─ Persist TaxCodeSuggestion records (idempotent via unique constraint)
```

**Performance**: Tiers 1-3 are database queries (fast, < 1s for 100 items). Tier 4 batches remaining items into a single LLM call (< 10s). Total < 15s for 100 items.

### D3: BAS Calculator Integration

The `GSTCalculator` is modified minimally:
1. Add `excluded_items: list[dict]` to `GSTResult.__init__`
2. In `_process_line_item()` and `_process_transaction_line_item()`, when `mapping["field"] == "excluded"`, append item details to `excluded_items` instead of silently returning
3. The calculator still excludes these from BAS fields — the suggestion engine runs after calculation

For recalculation after approvals:
1. Load active `TaxCodeOverride` records for the connection
2. Build a lookup dict: `(source_type, source_id, line_item_index) → override_tax_type`
3. In `_process_line_item()`, before checking `TAX_TYPE_MAPPING`, check the override lookup
4. If an override exists, use `override_tax_type` instead of the item's `tax_type`

### D4: Approval Gate

Modify `BASService.get_summary()` to add:
- `unresolved_exclusions_count`: number of `TaxCodeSuggestion` records with `status = 'pending'`
- If > 0, add to `blocking_issues`: "X transactions have unresolved tax codes"
- Set `can_approve = False` when unresolved exclusions exist

### D5: Re-sync Conflict Detection

During the Xero upsert flow (after `upsert_from_xero` returns):
1. Check if any active `TaxCodeOverride` exists for this entity
2. Compare the incoming Xero `line_items[index].tax_type` with `override.original_tax_type`
3. If Xero's value changed:
   - If it now matches `override.override_tax_type`: clear the override (Xero caught up)
   - If it's something else: set `conflict_detected = True`, store `xero_new_tax_type`

This logic belongs in a post-sync hook, not in the upsert itself, to keep the upsert clean.
