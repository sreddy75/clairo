# Research: AI Tax Code Resolution for BAS Preparation

**Branch**: `046-ai-tax-code-resolution` | **Date**: 2026-03-14

## R1: Where Unmapped Transactions Are Lost

**Decision**: Hook into `GSTCalculator._process_line_item()` and `_process_transaction_line_item()` to capture excluded items during calculation, rather than scanning transactions separately.

**Rationale**: The calculator already iterates every line item and checks `TAX_TYPE_MAPPING` at `calculator.py:340`. Adding a collector here means we detect exactly what the calculator excludes — no divergence between detection and calculation logic. The alternative (scanning transactions independently) would duplicate the mapping logic and risk drift.

**Implementation**: Add an `excluded_items: list[dict]` to `GSTResult`. When `mapping["field"] == "excluded"`, append the item details instead of silently returning. After calculation, persist these as `TaxCodeSuggestion` records.

## R2: Tax Code Suggestion Tiers — Data Availability

**Decision**: 4-tier waterfall: account default → same-client history → cross-client history → LLM.

**Rationale**:
- **Tier 1 (account default)**: `XeroAccount.default_tax_type` is synced from Xero for every account. Most Xero accounts have a default. This is the strongest signal because it's what the accountant (or Xero setup) already decided for that account.
- **Tier 2 (same-client history)**: Query all invoices and bank transactions for this `connection_id` where the same `account_code` appears with a valid (non-excluded) tax type. Aggregate by tax type, suggest the dominant one if ≥ 90% match.
- **Tier 3 (cross-client)**: Same query across all connections within the `tenant_id`. Broader signal but same accounting practice conventions.
- **Tier 4 (LLM)**: Send transaction description, amount, account name/type, and BAS context to Claude. Include the TAX_TYPE_MAPPING as a reference for the model.

**Key finding**: There is NO `get_by_account_code()` on `XeroAccountRepository`. The plan should bulk-fetch accounts with `list_by_connection()` and build an in-memory dict keyed by `account_code`.

## R3: Local Override vs Xero Write-Back

**Decision**: V1 applies tax codes locally only by updating `line_items` JSONB. No Xero write-back.

**Rationale**: The `XeroClient` has zero PUT/POST/PATCH methods for data — it's read-only. Adding write-back requires Xero API scope changes, rate limit management for writes, and error handling for partial failures. This is a separate spec.

**Conflict handling**: The Xero upsert pattern (`ON CONFLICT DO UPDATE`) overwrites the entire `line_items` JSONB on re-sync. To preserve local overrides:
- Store overrides in a separate `TaxCodeOverride` table (not in the JSONB directly)
- The BAS calculator reads overrides and applies them on top of Xero data during calculation
- On re-sync, compare incoming Xero `tax_type` with the override: if Xero now matches, clear the override; if Xero changed to something different, flag as conflict

**Alternative rejected**: Modifying the Xero upsert to skip `line_items` when overrides exist. This would create stale Xero data and break other features that depend on current Xero state.

## R4: Module Placement

**Decision**: Add to the existing `bas/` module, not a new top-level module.

**Rationale**: Tax code resolution is tightly coupled to BAS calculation — it reads the same transactions, uses the same `TAX_TYPE_MAPPING`, and triggers BAS recalculation. Creating a separate module would require cross-module calls for every operation. The BAS module already has 15 files; adding `tax_code_service.py`, `tax_code_models.py`, and related files follows the existing pattern of specialized services within BAS (like `lodgement_service.py`, `workboard_service.py`).

**Alternative rejected**: Standalone `tax_code_resolution/` module. Would require importing BAS internals (calculator, models, service) which violates the "no cross-module internal imports" rule.

## R5: Audit Trail Pattern

**Decision**: Use `BASAuditLog` with new event types, not a separate audit table.

**Rationale**: The `BASAuditLog` model already has `event_type` (string), `event_metadata` (JSON), and `session_id` (FK). Tax code resolution events are BAS session events — they belong in the same audit trail. Adding new `BASAuditEventType` values (e.g., `TAX_CODE_SUGGESTION_APPROVED`, `TAX_CODE_BULK_APPROVED`) follows the existing pattern.

## R6: BAS Approval Gate

**Decision**: Block BAS approval when unresolved excluded transactions exist.

**Rationale**: The `BASSummary` already has `can_approve` and `blocking_issues` fields computed at `service.py:893-909`. The quality gate checks quality score ≥ 70% and critical issue count = 0. Adding a check for "unresolved excluded transactions > 0" fits naturally. The frontend already reads `blocking_issues` (though it doesn't currently enforce them — that's a separate concern).

## R7: Post-Sync Pipeline Integration

**Decision**: Add `"tax_code_suggestions"` to `PHASE_POST_SYNC_TASKS[2]` to run after BAS calculation.

**Rationale**: The suggestion engine depends on BAS calculation having already identified the period's transactions. Phase 2 post-sync already runs `quality_score`, `bas_calculation`, and `aggregation`. Tax code suggestions should run after `bas_calculation` completes. The `PostSyncTask` tracking model already supports arbitrary task types.

**Note**: For the initial implementation, suggestions can also be triggered manually via an API endpoint (on-demand when the accountant opens the BAS session), not only post-sync. The Celery task is for automation; the endpoint is for interactive use.

## R8: Frontend Integration Point

**Decision**: Add tax code resolution UI within the existing `BASTab.tsx` component, not a separate page.

**Rationale**: `BASTab.tsx` is the accountant's BAS workspace (1875 lines). The exclusion banner and resolution panel should appear between the hero summary and the detail tabs — visible immediately after calculation. The unused `BASReviewPanel.tsx` (A2UI) could be repurposed but would add complexity; a simpler approach is inline UI within the existing component.

**UI components needed**:
- Exclusion banner (count + dollar impact, shown on hero panel)
- Resolution panel (expandable, shows suggestions grouped by confidence)
- Individual suggestion card (transaction details + suggestion + approve/reject/override)
- Bulk approve button (for high-confidence suggestions)
- Tax code dropdown (for manual override)
