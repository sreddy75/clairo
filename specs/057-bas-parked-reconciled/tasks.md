# Tasks: BAS Transaction Grouping by Xero Reconciliation Status

**Input**: Design documents from `specs/057-bas-parked-reconciled/`
**Branch**: `057-bas-parked-reconciled` (already created)
**Prerequisites**: plan.md ✅, spec.md ✅, research.md ✅, data-model.md ✅, contracts/api.md ✅, quickstart.md ✅

**Tests**: Not explicitly requested — no test tasks generated.

**Organization**: Tasks grouped by user story. US1 (auto-park) and US2 (reconciled section) are both P1 and tightly coupled on the backend foundation — the Foundational phase covers all shared backend plumbing. US3 (refresh) is P2 and fully independent.

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no dependencies on incomplete tasks in the same phase)
- **[Story]**: Which user story this task belongs to

---

## Phase 0: Git Setup

**Purpose**: Confirm branch exists before any implementation

- [X] T000 Confirm working branch is `057-bas-parked-reconciled`
  - Run: `git branch --show-current`
  - Expected output: `057-bas-parked-reconciled`
  - If not on this branch: `git checkout 057-bas-parked-reconciled`

---

## Phase 1: Setup — Migration

**Purpose**: Database schema change that all phases depend on

- [X] T001 Create Alembic migration adding `is_reconciled` and `auto_park_reason` to `tax_code_suggestions` in `backend/app/alembic/versions/20260413_add_reconciliation_fields_to_suggestions.py`
  - `is_reconciled`: `Boolean, nullable=True`
  - `auto_park_reason`: `String(50), nullable=True`
  - Index: `ix_tax_code_suggestions_session_reconciled` on `(session_id, is_reconciled)`
  - Downgrade must drop index then columns
  - Run: `cd backend && uv run alembic upgrade head` to verify migration applies cleanly

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Shared backend plumbing used by both US1 (auto-park) and US2 (reconciled section). Must complete before any user story work.

**⚠️ CRITICAL**: No user story implementation can begin until this phase is complete.

- [X] T002 Add `is_reconciled: Mapped[bool | None]` and `auto_park_reason: Mapped[str | None]` fields to `TaxCodeSuggestion` in `backend/app/modules/bas/models.py`
  - `is_reconciled = mapped_column(Boolean, nullable=True, default=None)`
  - `auto_park_reason = mapped_column(String(50), nullable=True, default=None)`

- [X] T003 [P] Add `is_reconciled: bool | None` and `auto_park_reason: str | None` to `TaxCodeSuggestionResponse` Pydantic schema in `backend/app/modules/bas/schemas.py`

- [X] T004 [P] Add `get_reconciliation_status_map(connection_id: UUID, xero_transaction_ids: list[str]) -> dict[str, bool]` to the Xero integration service public interface in `backend/app/modules/integrations/xero/service.py`
  - Query: `SELECT xero_transaction_id, is_reconciled FROM xero_bank_transactions WHERE connection_id = ? AND xero_transaction_id = ANY(?)`
  - Returns dict mapping xero_transaction_id string → `is_reconciled` bool
  - Must include `tenant_id` in query for RLS

- [X] T005 [P] Add `is_reconciled: boolean | null` and `auto_park_reason: string | null` fields to the `TaxCodeSuggestion` TypeScript interface in `frontend/src/lib/bas.ts`

**Checkpoint**: Migration applied, model updated, Xero service method available, TypeScript type extended. US1 and US2 implementation can now begin.

---

## Phase 3: User Story 1 — Unreconciled Transactions Auto-Parked (Priority: P1) 🎯 MVP

**Goal**: When `generate_suggestions` runs, unreconciled bank transactions are automatically placed in the Parked state with `auto_park_reason = "unreconciled_in_xero"`. The Parked section in the UI shows a distinguishing badge on auto-parked items.

**Independent Test**: Open a BAS session that has unreconciled bank transactions. Trigger suggestion generation (`POST .../tax-code-suggestions/generate`). Verify all bank-transaction suggestions where the underlying `XeroBankTransaction.is_reconciled = False` are returned with `status = "dismissed"` and `auto_park_reason = "unreconciled_in_xero"`. Verify they appear in the "Parked" accordion section with the "Unreconciled in Xero" badge.

- [X] T006 [US1] Add `get_bank_transaction_source_ids(session_id: UUID, tenant_id: UUID) -> list[str]` to `BASRepository` in `backend/app/modules/bas/repository.py`
  - Query: `SELECT DISTINCT CAST(source_id AS TEXT) FROM tax_code_suggestions WHERE session_id=? AND tenant_id=? AND source_type='bank_transaction'`

- [X] T007 [US1] Extend `generate_suggestions()` in `backend/app/modules/bas/service.py` to populate `is_reconciled` and auto-park unreconciled bank transactions before calling `bulk_create_suggestions()`
  - After building suggestion objects: call `get_bank_transaction_source_ids()` to get all bank transaction IDs
  - Call `xero_service.get_reconciliation_status_map(connection_id, xero_ids)` to fetch current `is_reconciled` values
  - For each suggestion where `source_type == "bank_transaction"`: set `s.is_reconciled = reconciled_map.get(str(s.source_id), False)`
  - If `s.is_reconciled is False`: set `s.status = "dismissed"` and `s.auto_park_reason = "unreconciled_in_xero"`
  - Non-bank suggestions: leave `is_reconciled = None` and `auto_park_reason = None`
  - Note: `bulk_create_suggestions` uses `ON CONFLICT DO NOTHING` — existing rows are never overwritten

- [X] T008 [US1] Emit `transaction.auto_parked` audit events in `generate_suggestions()` in `backend/app/modules/bas/service.py`
  - After `bulk_create_suggestions()` completes, for each newly inserted suggestion with `auto_park_reason = "unreconciled_in_xero"`, call `audit_event()` with event type `"transaction.auto_parked"`, capturing `session_id`, `source_id` (as `transaction_id`), and `reason = "auto_parked_unreconciled"`

- [X] T009 [P] [US1] Show "Unreconciled in Xero" badge on auto-parked suggestion rows in `frontend/src/components/bas/TaxCodeSuggestionCard.tsx`
  - When `suggestion.auto_park_reason === 'unreconciled_in_xero'`: render a small amber badge/chip (e.g. `<Badge variant="outline" className="text-amber-600 border-amber-300">Unreconciled in Xero</Badge>`) adjacent to the "Parked" status indicator
  - Render nothing extra when `auto_park_reason` is null (manually parked items unchanged)

**Checkpoint**: US1 is independently complete. Running `generate_suggestions` auto-parks unreconciled bank transactions. The Parked section shows a distinguishing badge. Manually parked items are unaffected.

---

## Phase 4: User Story 2 — Reconciled Transactions in Collapsible Section (Priority: P1)

**Goal**: The BAS tax code resolution panel shows a new "Reconciled" accordion section (collapsed by default) grouping all suggestions where `is_reconciled === true`. The section header shows count and an optional "N need review" warning.

**Independent Test**: Open a BAS session with reconciled bank transactions (suggestions where `is_reconciled = true`). The "Reconciled" accordion section appears below the existing sections, collapsed by default, showing "Reconciled (N)". Expanding it shows the reconciled items. If any reconciled suggestion has `status = 'pending'`, the header shows "Reconciled (N — M need review)".

- [X] T010 [US2] Extend `get_suggestion_summary()` in `backend/app/modules/bas/repository.py` to include three new scalar counts:
  - `reconciled_count`: `COUNT(*) WHERE session_id=? AND tenant_id=? AND is_reconciled=True`
  - `reconciled_needs_review_count`: `COUNT(*) WHERE … AND is_reconciled=True AND status='pending'`
  - `auto_parked_count`: `COUNT(*) WHERE … AND auto_park_reason='unreconciled_in_xero'`

- [X] T011 [P] [US2] Add `reconciled_count: int`, `reconciled_needs_review_count: int`, and `auto_parked_count: int` to `TaxCodeSuggestionSummary` Pydantic schema in `backend/app/modules/bas/schemas.py` and add corresponding fields to the `TaxCodeSuggestionSummary` TypeScript interface in `frontend/src/lib/bas.ts`

- [X] T012 [US2] Add a `reconciled` bucket to the suggestion bucketing logic in `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - New bucket: `const reconciled = suggestions.filter(s => s.is_reconciled === true)`
  - Exclude reconciled suggestions from existing buckets: add `&& s.is_reconciled !== true` guard to `highConfidence`, `needsReview`, `manual`, `resolved`, and `parked` filter predicates
  - Note: `parked` bucket keeps all `status === 'dismissed' || 'rejected'` regardless of `is_reconciled` — the parked bucket is for manual park actions; reconciled filter is the primary grouping

- [X] T013 [US2] Add the "Reconciled" `AccordionItem` to `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - Render after all existing accordion sections (high confidence, needs review, manual, parked, resolved)
  - Do NOT add `"reconciled"` to the default `openSections` array — must be collapsed by default
  - Trigger text: `reconciled_needs_review_count > 0 ? \`Reconciled (${reconciled.length} — ${reconciled_needs_review_count} need review)\` : \`Reconciled (${reconciled.length})\``
  - When `reconciled.length === 0` and all other buckets also have items: render nothing (no empty section)
  - When ALL suggestions are reconciled (all other buckets empty): still render the section with the count, plus a subtle note: "All transactions are reconciled in Xero"
  - Content: reuse existing `<SuggestionTable>` component with the `reconciled` array; pass `showActions={true}` so accountants can still approve/override from this section

**Checkpoint**: US1 + US2 complete. Unreconciled transactions auto-park on generation. Reconciled transactions appear in a collapsible section. Both work independently.

---

## Phase 5: User Story 3 — Refresh Reconciliation Status (Priority: P2)

**Goal**: Accountant can click "Refresh reconciliation status" to re-fetch Xero `IsReconciled` values for all bank-transaction suggestions in the session. Auto-parked suggestions that are now reconciled move to the Reconciled section. Pending suggestions that are now unreconciled are auto-parked. Accountant decisions are never overwritten.

**Independent Test**: In a BAS session, manually reconcile a transaction in Xero. Click "Refresh reconciliation status" in Clairo. Verify the suggestion moves from the Parked section to the Reconciled section within 5 seconds. Verify previously approved/overridden suggestions are unchanged.

- [X] T014 [US3] Add `apply_reconciliation_refresh(session_id: UUID, tenant_id: UUID, reconciled_map: dict[str, bool]) -> int` to `BASRepository` in `backend/app/modules/bas/repository.py`
  - For each `(xero_id, is_reconciled_now)` in `reconciled_map`:
    - Fetch all suggestions for this session/tenant where `source_type='bank_transaction'` and `source_id = UUID(xero_id)`
    - Skip suggestions where `status IN ('approved', 'overridden')` — never touch acted-on rows
    - If `is_reconciled_now=True` and `suggestion.auto_park_reason == "unreconciled_in_xero"`: set `status='pending'`, `auto_park_reason=None`, `is_reconciled=True` → reclassified += 1
    - If `is_reconciled_now=False` and `suggestion.status == 'pending'` and `suggestion.auto_park_reason is None`: set `status='dismissed'`, `auto_park_reason='unreconciled_in_xero'`, `is_reconciled=False` → reclassified += 1
    - Always update `is_reconciled` on the row to match current Xero value
  - `flush()` after all updates; return total reclassified count

- [X] T015 [US3] Add `refresh_reconciliation_status(session_id: UUID, tenant_id: UUID, connection_id: UUID) -> dict` to `BASService` in `backend/app/modules/bas/service.py`
  - Call `bas_repo.get_bank_transaction_source_ids(session_id, tenant_id)` → `source_ids`
  - If `source_ids` is empty, return `{"reclassified_count": 0, "newly_reconciled": 0, "newly_unreconciled": 0}`
  - Call `xero_service.get_reconciliation_status_map(connection_id, source_ids)` — wrap in try/except for Xero connection errors; raise domain exception `XeroConnectionUnavailableError` on failure (do not expose HTTP details in service layer)
  - Call `bas_repo.apply_reconciliation_refresh(session_id, tenant_id, reconciled_map)`
  - Emit `transaction.reconciliation_refreshed` audit event: `session_id`, `reclassified_count`, `refresh_source="manual"`
  - For each reclassification where new `is_reconciled=True`: emit `transaction.moved_to_reconciled` audit event
  - Commit and return `{"reclassified_count": N, "newly_reconciled": N2, "newly_unreconciled": N3}`

- [X] T016 [US3] Add `POST /clients/{connection_id}/bas/sessions/{session_id}/tax-code-suggestions/refresh-reconciliation` endpoint to `backend/app/modules/bas/router.py`
  - Call `bas_service.refresh_reconciliation_status(session_id, tenant_id, connection_id)`
  - On `XeroConnectionUnavailableError`: raise `HTTPException(503, detail="Xero connection unavailable", headers={"X-Error-Code": "xero_connection_unavailable"})`
  - On success: return `{"data": {"reclassified_count": N, "newly_reconciled": N2, "newly_unreconciled": N3}}`
  - Auth: same Clerk JWT dependency as other suggestion endpoints

- [X] T017 [P] [US3] Add `refreshReconciliationStatus(connectionId: string, sessionId: string): Promise<{reclassified_count: number, newly_reconciled: number, newly_unreconciled: number}>` API function to `frontend/src/lib/bas.ts`
  - `POST /clients/{connectionId}/bas/sessions/{sessionId}/tax-code-suggestions/refresh-reconciliation`
  - Return the `data` object from the API response
  - Throw on non-2xx (caller handles 503 for Xero unavailability)

- [X] T018 [US3] Add "Refresh reconciliation status" button to `frontend/src/components/bas/TaxCodeResolutionPanel.tsx`
  - Place near the panel header or alongside the existing bulk actions area
  - On click: call `refreshReconciliationStatus()`, then call `loadSuggestions()` to refresh the full list
  - Show a loading spinner on the button while the request is in flight (disable button during request)
  - On success: toast "Reconciliation status updated — N transactions reclassified" (or "No changes" if `reclassified_count === 0`)
  - On 503 error: toast "Unable to refresh — Xero connection unavailable"
  - Only render button when the session has bank-transaction suggestions (`summary.auto_parked_count > 0 || summary.reconciled_count > 0`)

**Checkpoint**: US3 complete. Refresh button live. Reclassification works without touching accountant decisions. Xero unavailability shows a clear message.

---

## Phase 6: Polish & Cross-Cutting Concerns

- [X] T019 [P] Add `XeroConnectionUnavailableError` to `backend/app/modules/bas/exceptions.py` if not already present (check `backend/app/core/exceptions.py` first — may already be a base class)

- [X] T020 [P] Verify existing `dismiss_suggestion` and `unpark_suggestion` endpoints in `backend/app/modules/bas/router.py` continue to work correctly with auto-parked suggestions
  - Approving an auto-parked suggestion must clear it from the Parked section (status → `approved`)
  - Overriding an auto-parked suggestion must clear it from the Parked section (status → `overridden`)
  - "Back to Manual" (`unpark`) on an auto-parked suggestion must set `status = 'pending'` and `auto_park_reason = None` — NOT tied to `is_reconciled`

- [X] T021 [P] Verify edge case: sessions created before this feature (existing suggestions have `is_reconciled = NULL`) display correctly
  - `NULL` suggestions must not appear in the Reconciled section (`is_reconciled === true` check)
  - `NULL` suggestions must flow through existing confidence buckets unchanged
  - Manual test: open a pre-existing session and confirm no regressions

- [X] T022 Run full validation per CLAUDE.md:
  - `cd backend && uv run ruff check . && uv run ruff format . && uv run pytest -k "suggestion or reconcil"`
  - `cd frontend && npm run lint && npx tsc --noEmit`

---

## Phase Final: PR & Merge

- [ ] T023 Push feature branch to remote
  - Run: `git push -u origin 057-bas-parked-reconciled`

- [ ] T024 Create pull request
  - Run: `gh pr create --title "feat: BAS reconciliation grouping — auto-park unreconciled, collapsible reconciled section" --body "..."`
  - PR body must reference spec `057-bas-parked-reconciled` and list schema changes (`tax_code_suggestions` +2 columns)

- [ ] T025 Update `specs/ROADMAP.md` — mark `057-bas-parked-reconciled` as COMPLETE after merge

---

## Dependencies & Execution Order

### Phase Dependencies

```
Phase 0 (Git) → Phase 1 (Migration) → Phase 2 (Foundational) → Phase 3 (US1) + Phase 4 (US2) [parallel]
                                                                 → Phase 5 (US3) [after US1+US2 or independently]
                                                                 → Phase 6 (Polish) → Phase Final
```

### User Story Dependencies

- **US1 (P1)**: Requires Phase 2 complete. No dependency on US2.
- **US2 (P1)**: Requires Phase 2 complete. No dependency on US1.
- **US3 (P2)**: Requires Phase 2 complete. Independent of US1 and US2 (no shared files in US3 phase).
- **US1 + US2** can be worked in parallel once Foundational is done.

### Within Each Phase

- T002 (model) before T003, T004, T005 (schemas/services that depend on the model fields)
- T006 (repository helper) before T007 (service that calls it)
- T007 (generate_suggestions extended) before T008 (audit events added to same method)
- T010 (repository summary counts) before T011 (schema)
- T014 (repository refresh) before T015 (service that calls it)
- T015 (service) before T016 (router that calls it)
- T017 (API function) before T018 (component that calls it)

---

## Parallel Opportunities

```bash
# Phase 2 — all four can run simultaneously (different files):
Task T003: schemas.py — TaxCodeSuggestionResponse fields
Task T004: xero/service.py — get_reconciliation_status_map()
Task T005: bas.ts — TypeScript type extension

# Phase 3 — T009 can run in parallel with T006-T008 (different file):
Task T009: TaxCodeSuggestionCard.tsx — badge (frontend, no backend dependency)

# Phase 4 — T011 can run in parallel with T012/T013 after T010:
Task T011: schemas.py + bas.ts — summary type extensions
Task T012: TaxCodeResolutionPanel.tsx — bucket logic (once T005 done)

# Phase 5 — T017 can run in parallel with T014-T016 (frontend only):
Task T017: bas.ts — refreshReconciliationStatus() API function
```

---

## Implementation Strategy

### MVP First (US1 + US2 — both P1)

1. Complete Phase 0–2 (Git, Migration, Foundational)
2. Complete Phase 3 (US1) — auto-park on generation
3. Complete Phase 4 (US2) — reconciled accordion section
4. **STOP and VALIDATE**: generate suggestions for a client with mixed reconciliation status; confirm grouping is correct
5. Deploy MVP

### Incremental Addition

6. Complete Phase 5 (US3) — refresh button
7. Complete Phase 6 (Polish) — edge case validation
8. PR and merge

### Total Task Count: 25 tasks (T000–T025)

| Phase | Tasks | Parallelizable |
|-------|-------|---------------|
| Phase 0 | 1 | 0 |
| Phase 1 | 1 | 0 |
| Phase 2 (Foundational) | 4 | 3 |
| Phase 3 (US1) | 4 | 1 |
| Phase 4 (US2) | 4 | 2 |
| Phase 5 (US3) | 5 | 2 |
| Phase 6 (Polish) | 4 | 3 |
| Phase Final | 3 | 0 |

---

## Notes

- `bulk_create_suggestions` uses `ON CONFLICT DO NOTHING` — auto-park values set before insert are safe; re-running generation does not overwrite existing rows
- Cross-module access: `bas/service.py` calls `xero/service.py` public interface only — never imports `XeroBankTransaction` model directly
- `tenant_id` must appear in every new repository query
- Domain exceptions in service layer; `HTTPException` only in router (Constitution §VI)
- `flush()` not `commit()` in repository methods — session lifecycle managed by caller
