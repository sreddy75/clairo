# Tasks: AI Tax Code Resolution for BAS Preparation

**Input**: Design documents from `/specs/046-ai-tax-code-resolution/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Organization**: Tasks grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2)
- Exact file paths included in descriptions

---

## Phase 0: Git Setup

**Purpose**: Feature branch already exists

- [x] T000 Verify on branch `046-ai-tax-code-resolution` and pull latest main
  - Run: `git checkout 046-ai-tax-code-resolution && git merge main`
  - Verify: Branch is up to date with main

---

## Phase 1: Foundational (Models, Migration, Exceptions)

**Purpose**: Shared data layer required by ALL user stories

- [x] T001 Add enums `TaxCodeSuggestionSourceType`, `TaxCodeSuggestionStatus`, `ConfidenceTier` and new `BASAuditEventType` values to `backend/app/modules/bas/models.py`
  - Add 3 new enums: `TaxCodeSuggestionSourceType` (invoice, bank_transaction, credit_note), `TaxCodeSuggestionStatus` (pending, approved, rejected, overridden, dismissed), `ConfidenceTier` (account_default, client_history, tenant_history, llm_classification, manual)
  - Add 8 new values to existing `BASAuditEventType` enum per data-model.md

- [x] T002 Add `TaxCodeSuggestion` model to `backend/app/modules/bas/models.py`
  - All fields per data-model.md: id, tenant_id, session_id, source_type, source_id, line_item_index, line_item_id, original_tax_type, suggested_tax_type, applied_tax_type, confidence_score, confidence_tier, suggestion_basis, status, resolved_by, resolved_at, dismissal_reason, account_code, account_name, description, line_amount, tax_amount, contact_name, transaction_date, created_at, updated_at
  - FKs: tenant_id → tenants.id, session_id → bas_sessions.id, resolved_by → practice_users.id
  - Unique constraint: `uq_tax_code_suggestion_session_source_line` on (session_id, source_type, source_id, line_item_index)
  - Indexes: tenant_id, session_id, (source_type, source_id)

- [x] T003 Add `TaxCodeOverride` model to `backend/app/modules/bas/models.py`
  - All fields per data-model.md: id, tenant_id, connection_id, source_type, source_id, line_item_index, original_tax_type, override_tax_type, applied_by, applied_at, suggestion_id, is_active, conflict_detected, xero_new_tax_type, conflict_resolved_at, created_at, updated_at
  - FKs: tenant_id → tenants.id, connection_id → xero_connections.id, applied_by → practice_users.id, suggestion_id → tax_code_suggestions.id
  - Partial unique constraint: `uq_tax_code_override_active` on (connection_id, source_type, source_id, line_item_index) WHERE is_active = true

- [x] T004 Create Alembic migration for `tax_code_suggestions` and `tax_code_overrides` tables in `backend/alembic/versions/`
  - Run: `cd backend && uv run alembic revision --autogenerate -m "add tax code resolution tables"`
  - Verify migration creates both tables with all indexes and constraints
  - Test: `cd backend && uv run alembic upgrade head`

- [x] T005 [P] Add domain exceptions to `backend/app/modules/bas/exceptions.py`
  - Add `SuggestionNotFoundError(DomainError)` with status_code 404
  - Add `SuggestionAlreadyResolvedError(DomainError)` with status_code 409
  - Add `InvalidTaxTypeError(DomainError)` with status_code 422
  - Add `SessionNotEditableForSuggestionsError(DomainError)` with status_code 409
  - Add `NoApprovedSuggestionsError(DomainError)` with status_code 409
  - Add `OverrideNotFoundError(DomainError)` with status_code 404
  - All extend `DomainError` from `app.core.exceptions` (not plain Exception)

- [x] T006 [P] Add Pydantic schemas to `backend/app/modules/bas/schemas.py`
  - Request schemas: `ApproveSuggestionRequest`, `RejectSuggestionRequest`, `OverrideSuggestionRequest`, `DismissSuggestionRequest`, `BulkApproveRequest`, `ResolveConflictRequest`
  - Response schemas: `TaxCodeSuggestionResponse`, `TaxCodeSuggestionListResponse`, `TaxCodeSuggestionSummaryResponse`, `GenerateSuggestionsResponse`, `BulkApproveResponse`, `RecalculateResponse`, `ConflictResponse`, `ConflictListResponse`, `ResolveConflictResponse`
  - Use field validators for `tax_type` (must be valid key in TAX_TYPE_MAPPING, not excluded)
  - Follow existing Pydantic v2 patterns in schemas.py

**Checkpoint**: Data layer ready — all models, migration, exceptions, and schemas in place.

---

## Phase 2: User Story 1 — See What's Missing from the BAS (P1)

**Goal**: After BAS calculation, the accountant sees a banner showing how many transactions were excluded and their total dollar impact. Clicking reveals individual excluded items.

**Independent Test**: Import Xero data with NONE/BASEXCLUDED tax types → calculate BAS → verify banner shows count and dollar amount → click to see transaction list.

### Implementation

- [x] T007 [US1] Modify `GSTResult` to capture excluded items in `backend/app/modules/bas/calculator.py`
  - Add `excluded_items: list[dict]` field to `GSTResult.__init__` (initialize as empty list)
  - In `_process_line_item()` at line ~344 (where `mapping["field"] == "excluded"` returns early): instead of bare return, append item details to `self.excluded_items` with keys: source_type, source_id, line_item_index, tax_type, line_amount, tax_amount, account_code, description, line_item_id
  - Same change in `_process_transaction_line_item()` at line ~411
  - Pass source context (invoice/bank_transaction, source ID) into these methods so they can populate source_type and source_id
  - The calculator STILL excludes these from BAS fields — the append is tracking only

- [x] T008 [US1] Add suggestion repository methods to `backend/app/modules/bas/repository.py`
  - `create_suggestion(data: dict) -> TaxCodeSuggestion` — create with flush()
  - `bulk_create_suggestions(items: list[dict]) -> list[TaxCodeSuggestion]` — bulk insert with ON CONFLICT DO NOTHING on unique constraint (idempotency)
  - `get_suggestion(suggestion_id: UUID, tenant_id: UUID) -> TaxCodeSuggestion | None`
  - `list_suggestions(session_id: UUID, tenant_id: UUID, status: str | None, confidence_tier: str | None, min_confidence: float | None) -> list[TaxCodeSuggestion]`
  - `get_suggestion_summary(session_id: UUID, tenant_id: UUID) -> dict` — counts by status, total excluded amount, total resolved amount, high/medium/low confidence counts
  - `count_unresolved(session_id: UUID, tenant_id: UUID) -> int` — count where status = 'pending'
  - All queries MUST include `tenant_id` filter

- [x] T009 [US1] Create `TaxCodeService` with excluded item detection in `backend/app/modules/bas/tax_code_service.py`
  - `__init__(self, session: AsyncSession)` — initialize with DB session
  - `detect_excluded_items(session_id: UUID, tenant_id: UUID) -> list[dict]` — runs GSTCalculator for the session's period, returns GSTResult.excluded_items enriched with contact_name, account_name, transaction_date from source records
  - `persist_excluded_items(session_id: UUID, tenant_id: UUID, excluded_items: list[dict]) -> int` — creates TaxCodeSuggestion records with status='pending', no suggestion yet. Uses bulk_create_suggestions with ON CONFLICT DO NOTHING for idempotency. Returns count created.
  - `get_summary(session_id: UUID, tenant_id: UUID) -> dict` — returns summary for the exclusion banner (excluded_count, excluded_amount, resolved_count, unresolved_count, blocks_approval)
  - Fetch XeroAccounts via `list_by_connection()` to resolve account_code → account_name

- [x] T010 [US1] Add summary and list endpoints to `backend/app/modules/bas/router.py`
  - `GET /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/summary` — calls TaxCodeService.get_summary(), returns TaxCodeSuggestionSummaryResponse
  - `GET /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions` — calls repository.list_suggestions() with query params (status, confidence_tier, min_confidence), returns TaxCodeSuggestionListResponse
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/generate` — calls TaxCodeService.detect_excluded_items() then persist_excluded_items(), returns GenerateSuggestionsResponse. Validates session is editable.
  - Follow existing router patterns: tenant_id from request state, error handling via DomainError propagation

- [x] T011 [US1] Add suggestion summary API functions to `frontend/src/lib/bas.ts`
  - `getTaxCodeSuggestionSummary(token, connectionId, sessionId)` — GET summary endpoint
  - `listTaxCodeSuggestions(token, connectionId, sessionId, filters?)` — GET list endpoint
  - `generateTaxCodeSuggestions(token, connectionId, sessionId)` — POST generate endpoint
  - TypeScript types: `TaxCodeSuggestion`, `TaxCodeSuggestionSummary`, `GenerateSuggestionsResult`

- [x] T012 [US1] Add exclusion banner to `frontend/src/components/bas/BASTab.tsx`
  - After BAS calculation completes, fetch suggestion summary via `getTaxCodeSuggestionSummary`
  - Show amber warning banner between hero panel and detail tabs when `excluded_count > 0`: "X transactions ($Y) excluded from this BAS — tax codes needed"
  - Banner includes: AlertTriangle icon, count, formatted dollar amount, "Review" button
  - Hide banner when `excluded_count === 0`
  - Use shadcn Alert component with `variant="warning"`
  - Use `formatCurrency` from `@/lib/formatters`
  - On "Review" click: expand the resolution panel (US2) or scroll to excluded items list

**Checkpoint**: US1 complete — accountant can see excluded transaction count and dollar impact on the BAS screen.

---

## Phase 3: User Story 2 — Review and Approve AI Tax Code Suggestions (P1)

**Goal**: The system generates tax code suggestions using account defaults and historical patterns. The accountant can approve, reject, override, or dismiss suggestions individually or in bulk.

**Independent Test**: Generate suggestions for excluded items → verify account-default suggestions have 0.95 confidence → approve one → override another → bulk approve high-confidence → verify all resolved.

### Implementation

- [x] T013 [US2] Implement Tier 1 (account default) suggestion engine in `backend/app/modules/bas/tax_code_service.py`
  - `_suggest_from_account_default(account_code: str, accounts_map: dict) -> tuple[str | None, float, str]` — returns (suggested_tax_type, confidence, basis_text)
  - Bulk-fetch XeroAccounts for the connection via `list_by_connection()`, build dict keyed by account_code
  - For each excluded item: look up account_code → default_tax_type. If default_tax_type is a valid non-excluded key in TAX_TYPE_MAPPING, suggest it with confidence 0.95 and basis "Account {code} ({name}) has default tax type {type}"
  - If no default or default maps to excluded: return None (fall through to next tier)

- [x] T014 [US2] Implement Tier 2 (client history) suggestion engine in `backend/app/modules/bas/tax_code_service.py`
  - `_suggest_from_client_history(account_code: str, connection_id: UUID, session: AsyncSession) -> tuple[str | None, float, str]`
  - Query all invoices and bank transactions for this connection_id where any line_item has matching account_code AND a valid (non-excluded) tax_type
  - Use raw SQL with `jsonb_array_elements` to extract tax_types from line_items for the given account_code
  - Group by tax_type, count occurrences. If dominant type has ≥ 90% share, suggest it with confidence scaled 0.85-0.95 based on percentage. Basis: "X% of prior transactions on account {code} used {type} (N matches)"

- [x] T015 [US2] Implement Tier 3 (tenant history) suggestion engine in `backend/app/modules/bas/tax_code_service.py`
  - `_suggest_from_tenant_history(account_code: str, tenant_id: UUID, session: AsyncSession) -> tuple[str | None, float, str]`
  - Same query as Tier 2 but across ALL connections for the tenant_id (not just current connection)
  - If dominant type has ≥ 85% share, suggest with confidence 0.70-0.85. Basis: "X% of transactions across your practice on account {code} used {type} (N matches across M clients)"

- [x] T016 [US2] Implement suggestion generation orchestrator in `backend/app/modules/bas/tax_code_service.py`
  - `generate_suggestions(session_id: UUID, tenant_id: UUID) -> GenerateSuggestionsResult`
  - Run detect_excluded_items() to get current excluded items
  - For each item: run tiered waterfall (Tier 1 → 2 → 3), stop at first successful suggestion
  - Items not resolved by tiers 1-3 get status='pending' with no suggestion (Tier 4/LLM deferred to US6)
  - Update existing TaxCodeSuggestion records with suggestion data (suggested_tax_type, confidence_score, confidence_tier, suggestion_basis) via upsert
  - Skip items already resolved (approved/rejected/overridden/dismissed) — idempotency
  - Return breakdown: {account_default: N, client_history: N, tenant_history: N, no_suggestion: N, skipped_already_resolved: N}
  - Create BASAuditLog entry with event_type TAX_CODE_SUGGESTIONS_GENERATED

- [x] T017 [US2] Add resolution methods to `TaxCodeService` in `backend/app/modules/bas/tax_code_service.py`
  - `approve_suggestion(suggestion_id: UUID, tenant_id: UUID, user_id: UUID, notes: str | None) -> TaxCodeSuggestion` — set status=approved, applied_tax_type=suggested_tax_type, resolved_by, resolved_at. Raise SuggestionNotFoundError or SuggestionAlreadyResolvedError. Create audit log.
  - `reject_suggestion(suggestion_id: UUID, tenant_id: UUID, user_id: UUID, reason: str | None) -> TaxCodeSuggestion` — set status=rejected. Create audit log.
  - `override_suggestion(suggestion_id: UUID, tenant_id: UUID, user_id: UUID, tax_type: str, reason: str | None) -> TaxCodeSuggestion` — validate tax_type against TAX_TYPE_MAPPING (not excluded). Set status=overridden, applied_tax_type=tax_type. Create audit log.
  - `dismiss_suggestion(suggestion_id: UUID, tenant_id: UUID, user_id: UUID, reason: str | None) -> TaxCodeSuggestion` — set status=dismissed, dismissal_reason=reason. Create audit log.
  - `bulk_approve(session_id: UUID, tenant_id: UUID, user_id: UUID, min_confidence: float | None, confidence_tier: str | None) -> BulkApproveResult` — approve all pending suggestions matching criteria. Create single bulk audit log entry with count.

- [x] T018 [US2] Add resolution endpoints to `backend/app/modules/bas/router.py`
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/approve` — calls approve_suggestion
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/reject` — calls reject_suggestion
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/override` — calls override_suggestion
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/{suggestion_id}/dismiss` — calls dismiss_suggestion
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/bulk-approve` — calls bulk_approve
  - All endpoints validate session exists and is editable

- [x] T019 [US2] Add resolution API functions to `frontend/src/lib/bas.ts`
  - `approveSuggestion(token, connectionId, sessionId, suggestionId, notes?)` — POST approve
  - `rejectSuggestion(token, connectionId, sessionId, suggestionId, reason?)` — POST reject
  - `overrideSuggestion(token, connectionId, sessionId, suggestionId, taxType, reason?)` — POST override
  - `dismissSuggestion(token, connectionId, sessionId, suggestionId, reason?)` — POST dismiss
  - `bulkApproveSuggestions(token, connectionId, sessionId, minConfidence?, confidenceTier?)` — POST bulk-approve
  - TypeScript types for all request/response shapes

- [x] T020 [US2] Create `TaxCodeSuggestionCard` component in `frontend/src/components/bas/TaxCodeSuggestionCard.tsx`
  - Displays: source badge (INV/TXN/CN), description, contact_name, transaction_date, account_code + account_name, line_amount (formatted), original_tax_type
  - Suggestion section: suggested_tax_type with confidence badge (High/Medium/Low with green/amber/red), suggestion_basis text
  - Action buttons: Approve (green), Reject (outline), Override (dropdown trigger), Dismiss (subtle)
  - Override: opens dropdown of valid tax types from TAX_TYPE_MAPPING (non-excluded)
  - Dismissed state shows muted card with "Excluded — {reason}"
  - Resolved state shows checkmark with applied_tax_type
  - Use shadcn Card, Badge, Button, Select components
  - Use `cn()` for conditional classes, `formatCurrency` for amounts

- [x] T021 [US2] Create `TaxCodeBulkActions` component in `frontend/src/components/bas/TaxCodeBulkActions.tsx`
  - Sticky bar at top of resolution panel when pending suggestions exist
  - Shows: "X suggestions pending" count, "Approve All High Confidence (N)" button
  - Button calls bulkApproveSuggestions with min_confidence=0.90
  - After bulk approve: refresh suggestion list and summary banner
  - Use shadcn Button with variant="default" (coral CTA)

- [x] T022 [US2] Create `TaxCodeResolutionPanel` component in `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - Expandable panel triggered from the exclusion banner
  - Fetches suggestions via `listTaxCodeSuggestions` on mount
  - Groups suggestions by confidence tier: "High Confidence", "Needs Review", "Manual Required"
  - Each group shows count and renders TaxCodeSuggestionCard for each item
  - Includes TaxCodeBulkActions bar at top
  - After any action (approve/reject/override/dismiss): refresh the list and parent banner summary
  - Empty state: "All transactions resolved" with green checkmark
  - Use shadcn Accordion for tier groups, ScrollArea for long lists

- [x] T023 [US2] Integrate `TaxCodeResolutionPanel` into `frontend/src/components/bas/BASTab.tsx`
  - Import TaxCodeResolutionPanel
  - Render below the exclusion banner, conditionally visible when banner is expanded/clicked
  - Pass connectionId, sessionId, getToken as props
  - Wire up refresh callback: when resolution panel reports changes, re-fetch summary to update banner
  - Also trigger suggestion generation (POST generate) when panel first opens if no suggestions exist yet

**Checkpoint**: US2 complete — accountant can see AI suggestions with confidence levels, approve/reject/override individually, bulk approve high-confidence items.

---

## Phase 4: User Story 3 — BAS Recalculates After Approvals (P1)

**Goal**: After approving tax code suggestions, BAS figures automatically recalculate to include newly mapped transactions. The approval gate blocks BAS approval until all exclusions are resolved.

**Independent Test**: Approve a suggestion for an excluded $1000 INPUT purchase → trigger recalculate → verify G11 increases by $1000 and 1B increases by GST component → verify BAS cannot be approved while pending items remain.

### Implementation

- [x] T024 [US3] Add override repository methods to `backend/app/modules/bas/repository.py`
  - `create_override(data: dict) -> TaxCodeOverride` — create with flush()
  - `get_active_overrides(connection_id: UUID, tenant_id: UUID) -> list[TaxCodeOverride]` — WHERE is_active = true
  - `get_active_override(connection_id: UUID, source_type: str, source_id: UUID, line_item_index: int, tenant_id: UUID) -> TaxCodeOverride | None`
  - `deactivate_override(override_id: UUID, tenant_id: UUID)` — set is_active = false

- [x] T025 [US3] Modify `GSTCalculator` to apply overrides in `backend/app/modules/bas/calculator.py`
  - Add optional `overrides: dict | None` parameter to `calculate()` method
  - `overrides` is a dict keyed by `(source_type, source_id, line_item_index)` → `override_tax_type`
  - In `_process_line_item()`: before looking up `TAX_TYPE_MAPPING`, check if an override exists for this item. If so, use override's tax_type instead of the item's original tax_type
  - Same change in `_process_transaction_line_item()`
  - When override is applied, the item gets mapped to the correct BAS field instead of being excluded

- [x] T026 [US3] Add recalculation method to `TaxCodeService` in `backend/app/modules/bas/tax_code_service.py`
  - `apply_and_recalculate(session_id: UUID, tenant_id: UUID, user_id: UUID) -> RecalculateResult`
  - Step 1: Fetch all approved/overridden TaxCodeSuggestion records for this session that don't yet have a TaxCodeOverride
  - Step 2: Create TaxCodeOverride records for each (with link to suggestion_id)
  - Step 3: Fetch all active overrides for the connection
  - Step 4: Call GSTCalculator.calculate() with the overrides dict
  - Step 5: Save the new BASCalculation result via BASService
  - Step 6: Create audit log entry BAS_RECALCULATED_AFTER_RESOLUTION with before/after field values
  - Return: applied_count, field-by-field before/after comparison

- [x] T027 [US3] Add recalculate endpoint to `backend/app/modules/bas/router.py`
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/recalculate` — calls apply_and_recalculate(), returns RecalculateResponse
  - Validates session is editable and has approved suggestions

- [x] T028 [US3] Integrate approval gate into `backend/app/modules/bas/service.py`
  - In `get_summary()` method (around line 893): after existing quality gate checks, add check for unresolved tax code suggestions
  - Query `TaxCodeService.get_summary()` or `repository.count_unresolved(session_id, tenant_id)`
  - If unresolved_count > 0: add to `blocking_issues` list: f"{unresolved_count} transactions have unresolved tax codes"
  - Set `can_approve = False` when unresolved exclusions exist (in addition to existing quality gates)

- [x] T029 [US3] Add recalculate API function and wire into frontend `frontend/src/lib/bas.ts` and `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - Add `recalculateBAS(token, connectionId, sessionId)` API function to bas.ts
  - Add "Apply & Recalculate" button to TaxCodeResolutionPanel — shown when any approved/overridden suggestions exist that haven't been applied yet
  - After recalculate: refresh BAS hero panel (totals), variance tab, and suggestion summary
  - Show before/after comparison briefly (toast or inline diff)

**Checkpoint**: US3 complete — approved suggestions are applied, BAS recalculates with new figures, approval gate prevents lodging until all exclusions resolved.

---

## Phase 5: User Story 4 — Audit Trail for AI Suggestions and Approvals (P2)

**Goal**: Every AI suggestion, approval, rejection, and override is recorded in the BAS audit trail with full context.

**Independent Test**: Approve a suggestion → view BAS audit log → verify entry shows timestamp, user, original code, suggested code, applied code, confidence, and basis.

### Implementation

- [x] T030 [US4] Verify and enhance audit logging across all resolution methods in `backend/app/modules/bas/tax_code_service.py`
  - Audit log for approve: event_type=TAX_CODE_SUGGESTION_APPROVED, metadata includes original_tax_type, suggested_tax_type, applied_tax_type, confidence_score, confidence_tier, suggestion_basis, source_type, source_id, line_item_index
  - Audit log for reject: event_type=TAX_CODE_SUGGESTION_REJECTED, metadata includes suggested_tax_type, reason
  - Audit log for override: event_type=TAX_CODE_SUGGESTION_OVERRIDDEN, metadata includes suggested_tax_type, override_tax_type (applied), reason
  - Audit log for dismiss: event_type=TAX_CODE_TRANSACTION_DISMISSED, metadata includes original_tax_type, reason
  - Audit log for bulk approve: event_type=TAX_CODE_BULK_APPROVED, metadata includes count, min_confidence, confidence_tier filter
  - Audit log for generate: event_type=TAX_CODE_SUGGESTIONS_GENERATED, metadata includes breakdown by tier, total generated, skipped count
  - Audit log for recalculate: event_type=BAS_RECALCULATED_AFTER_RESOLUTION, metadata includes applied_count, field-by-field before/after
  - All use existing `repository.create_audit_log()` pattern with performed_by (user_id) or is_system_action=True for automated generation

- [x] T031 [US4] Add audit log entries to suggestion list response in `backend/app/modules/bas/router.py`
  - Add optional `include_audit=true` query param to GET /tax-code-suggestions
  - When enabled, include last audit event for each suggestion (resolved_by name, resolved_at, action taken)
  - This allows the frontend to show resolution history inline on each card

**Checkpoint**: US4 complete — full audit trail for all AI and human actions.

---

## Phase 6: User Story 5 — Re-sync Conflict Handling (P2)

**Goal**: When Xero data is re-synced after tax codes are applied locally, conflicts are detected and surfaced to the accountant.

**Independent Test**: Apply a tax code override → simulate re-sync with changed Xero data → verify conflict is flagged → resolve conflict by keeping override or accepting Xero.

### Implementation

- [x] T032 [US5] Implement conflict detection logic in `backend/app/modules/bas/tax_code_service.py`
  - `detect_conflicts(connection_id: UUID, tenant_id: UUID) -> list[dict]`
  - Fetch all active TaxCodeOverrides for the connection
  - For each override: load the source entity (XeroInvoice/XeroBankTransaction), read line_items[line_item_index].tax_type
  - Compare current Xero tax_type with override.original_tax_type:
    - If Xero unchanged (matches original): no conflict, override still valid
    - If Xero now matches override.override_tax_type: clear override (is_active=false), Xero caught up
    - If Xero changed to something else: set conflict_detected=true, xero_new_tax_type=new value, create audit log TAX_CODE_CONFLICT_DETECTED
  - Return list of newly detected conflicts

- [x] T033 [US5] Add conflict detection to post-sync pipeline in `backend/app/tasks/xero.py`
  - Add `"tax_code_conflict_check"` to `PHASE_POST_SYNC_TASKS[2]` (after bas_calculation)
  - Create new Celery task `check_tax_code_conflicts` in `backend/app/tasks/bas.py`
  - Task calls TaxCodeService.detect_conflicts() for the connection
  - Follows existing task patterns: bind=True, max_retries=3, retry_backoff, async wrapper with asyncio.run()
  - Register task in `backend/app/tasks/__init__.py`

- [x] T034 [US5] Implement conflict resolution in `backend/app/modules/bas/tax_code_service.py`
  - `resolve_conflict(override_id: UUID, tenant_id: UUID, user_id: UUID, resolution: str, reason: str | None) -> TaxCodeOverride`
  - If resolution == "keep_override": clear conflict_detected flag, set conflict_resolved_at, keep override active
  - If resolution == "accept_xero": deactivate override (is_active=false), set conflict_resolved_at. The override's suggestion should also be updated if the Xero value is now valid
  - Create audit log for resolution

- [x] T035 [US5] Add conflict endpoints to `backend/app/modules/bas/router.py`
  - `GET /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/conflicts` — lists active conflicts for this connection, returns ConflictListResponse
  - `POST /{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/conflicts/{override_id}/resolve` — calls resolve_conflict, returns ResolveConflictResponse

- [x] T036 [US5] Add conflict UI to `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - Add conflict API functions to `frontend/src/lib/bas.ts`: `getConflicts()`, `resolveConflict()`
  - Show conflict banner at top of resolution panel (red warning): "X conflicts detected — Xero data changed since your last review"
  - Conflict card shows: transaction details, "Your override: OUTPUT", "Xero now says: INPUT", two buttons: "Keep Mine" / "Accept Xero"
  - After resolution: refresh conflicts list and suggestion summary

**Checkpoint**: US5 complete — re-sync conflicts detected, surfaced, and resolvable.

---

## Phase 7: User Story 6 — LLM Classification for Ambiguous Transactions (P3)

**Goal**: Transactions that can't be classified by account defaults or historical patterns are sent to Claude for classification with human-readable reasoning.

**Independent Test**: Create excluded items with no account default and no historical pattern → generate suggestions → verify LLM-classified items have confidence 0.60-0.80 and readable reasoning.

### Implementation

- [x] T037 [US6] Implement Tier 4 (LLM classification) in `backend/app/modules/bas/tax_code_service.py`
  - `_suggest_from_llm(items: list[dict], accounts_map: dict) -> list[tuple[str | None, float, str]]`
  - Batch remaining unclassified items into a single Claude Sonnet call
  - Build prompt with: TAX_TYPE_MAPPING reference, Australian BAS context, for each item: description, amount, account_code, account_name, account_type, counterparty
  - Ask Claude to return JSON array with: suggested_tax_type, confidence (0.0-1.0), reasoning (human-readable)
  - Map Claude's confidence to 0.60-0.80 range. If Claude returns confidence < 0.5, mark as no_suggestion
  - Handle API errors gracefully: on failure, items remain as no_suggestion (manual review required)
  - Use anthropic SDK with claude-sonnet-4-20250514 model

- [x] T038 [US6] Integrate LLM tier into suggestion generation orchestrator in `backend/app/modules/bas/tax_code_service.py`
  - In `generate_suggestions()`: after tiers 1-3, collect remaining unclassified items
  - If any remain, call `_suggest_from_llm()` with the batch
  - Update TaxCodeSuggestion records with LLM results (suggested_tax_type, confidence_score, confidence_tier=llm_classification, suggestion_basis=Claude's reasoning)
  - Update generate response breakdown with llm_classification count

- [x] T039 [US6] Update frontend `TaxCodeSuggestionCard` to display LLM reasoning in `frontend/src/components/bas/TaxCodeSuggestionCard.tsx`
  - For suggestions with confidence_tier="llm_classification": show the suggestion_basis as an expandable "AI Reasoning" section
  - Use a subtle AI indicator (e.g., sparkle icon + "AI classified") to distinguish from deterministic suggestions
  - Show "Manual review required" state for items with no suggestion (no suggested_tax_type)

**Checkpoint**: US6 complete — ambiguous transactions get LLM classification with readable reasoning.

---

## Phase 8: Polish & Cross-Cutting Concerns

**Purpose**: Final integration, cleanup, and validation

- [x] T040 [P] Add Celery task for automated suggestion generation post-BAS-calculation in `backend/app/tasks/bas.py`
  - Create `generate_tax_code_suggestions` task following existing task patterns
  - Wire into `PHASE_POST_SYNC_TASKS[2]` in `backend/app/tasks/xero.py` — runs after bas_calculation
  - Task calls TaxCodeService.generate_suggestions() for each BAS session auto-calculated
  - Register in `backend/app/tasks/__init__.py`

- [x] T041 [P] Update `backend/app/modules/bas/__init__.py` exports
  - Export new models: TaxCodeSuggestion, TaxCodeOverride, enums
  - Export TaxCodeService
  - Export new schemas

- [x] T042 Register tax-code-suggestion routes in `backend/app/main.py`
  - Verify BAS router registration includes all new endpoints (they're added to existing router, so likely automatic)
  - If TaxCodeService needs its own router prefix, add `include_router` call

- [x] T043 Run full backend validation
  - Run: `cd backend && uv run ruff check . && uv run ruff format . && uv run pytest`
  - Fix any lint, format, or test failures
  - Verify migration applies cleanly: `cd backend && uv run alembic upgrade head`

- [x] T044 Run full frontend validation
  - Run: `cd frontend && npm run lint && npx tsc --noEmit`
  - Fix any lint or type errors
  - Verify dev server starts: `cd frontend && npm run dev`

---

## Phase FINAL: PR & Merge

- [ ] T045 Ensure all tests pass
  - Run: `cd backend && uv run ruff check . && uv run pytest && cd ../frontend && npm run lint && npx tsc --noEmit`

- [ ] T046 Push feature branch and create PR
  - Run: `git push -u origin 046-ai-tax-code-resolution`
  - Create PR with summary of changes referencing spec 046

- [ ] T047 Address review feedback (if any)

- [ ] T048 Merge PR to main

- [ ] T049 Update `specs/ROADMAP.md` — mark spec 046 as COMPLETE

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git Setup)**: Already done — branch exists
- **Phase 1 (Foundational)**: Must complete before any user story
- **Phase 2 (US1)**: Depends on Phase 1. Delivers exclusion visibility.
- **Phase 3 (US2)**: Depends on Phase 2 (needs excluded items). Delivers suggestion + review UI.
- **Phase 4 (US3)**: Depends on Phase 3 (needs approved suggestions). Delivers recalculation + approval gate.
- **Phase 5 (US4)**: Depends on Phase 3 (audit trails are added to resolution methods). Can run in parallel with Phase 4.
- **Phase 6 (US5)**: Depends on Phase 4 (needs TaxCodeOverride). Independent from US4 and US6.
- **Phase 7 (US6)**: Depends on Phase 3 (extends suggestion engine). Independent from US4 and US5.
- **Phase 8 (Polish)**: After all desired user stories complete.

### User Story Dependencies

```
Phase 1 (Foundational)
  └─→ US1 (See What's Missing) — P1
       └─→ US2 (Review & Approve Suggestions) — P1
            ├─→ US3 (Recalculate After Approvals) — P1
            ├─→ US4 (Audit Trail) — P2 [parallel with US3]
            └─→ US6 (LLM Classification) — P3 [parallel with US3, US4]
       └─→ US5 (Re-sync Conflicts) — P2 [after US3 for overrides]
```

### Parallel Opportunities

Within Phase 1:
- T005 (exceptions) and T006 (schemas) can run in parallel with T001-T003

Within Phase 3 (US2):
- T013, T014, T015 (suggestion tiers) can run in parallel
- T020, T021 (frontend components) can run in parallel

Within Phase 8 (Polish):
- T040, T041, T042 can all run in parallel

---

## Implementation Strategy

### MVP First (US1 Only — Phases 0-2)

1. Complete Phase 1: Models, migration, exceptions, schemas
2. Complete Phase 2: Calculator hook, summary endpoint, exclusion banner
3. **STOP and VALIDATE**: Accountant can see what's missing from BAS
4. This alone solves the immediate user testing feedback

### Core Delivery (US1 + US2 + US3 — Phases 0-4)

1. Complete MVP (above)
2. Add US2: Suggestion engine + review UI
3. Add US3: Recalculation + approval gate
4. **STOP and VALIDATE**: Full end-to-end flow working

### Full Feature (All Stories — Phases 0-8)

1. Complete Core Delivery (above)
2. Add US4: Audit trail verification
3. Add US5: Re-sync conflict handling
4. Add US6: LLM classification
5. Polish & PR

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Commit after each task or logical group
- All new code within existing `bas/` module — no new module creation
- All exceptions extend `DomainError` (not plain Exception)
- All repository methods use `flush()` not `commit()`
- All queries must include `tenant_id` for RLS
