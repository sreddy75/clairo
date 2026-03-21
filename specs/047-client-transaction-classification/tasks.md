# Tasks: Client Transaction Classification

**Input**: Design documents from `/specs/047-client-transaction-classification/`
**Prerequisites**: plan.md, spec.md, research.md, data-model.md, contracts/api.md, quickstart.md

**Tests**: Not explicitly requested in the spec. Tests omitted — add if needed.

**Organization**: Tasks grouped by user story. 6 user stories from spec.md.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup

- [x] T000 Verify feature branch `047-client-transaction-classification` exists and is checked out
  - Branch already created during planning
  - Verify: `git branch --show-current` returns `047-client-transaction-classification`

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Database migration, models, constants, and shared service scaffolding

- [x] T001 Create category taxonomy constants in `backend/app/modules/bas/classification_constants.py`
  - Define `CLASSIFICATION_CATEGORIES` list of dicts: `{id, label, group, typical_tax_type, receipt_required_always}`
  - Groups: "expense", "income", "special"
  - Include all 18 expense categories, 5 income categories, 3 special categories from spec.md
  - Define `RECEIPT_FLAG_RULES` dict with threshold ($82.50), vague description patterns, and always-flag category IDs
  - Define `VAGUE_DESCRIPTION_PATTERNS` list of regex patterns ("TRANSFER", "PAYMENT", "DIRECT DEBIT", "ATM", "EFT", short strings <5 chars)

- [x] T002 Create frontend category taxonomy in `frontend/src/lib/constants/classification-categories.ts`
  - Mirror backend `CLASSIFICATION_CATEGORIES` structure
  - Export `EXPENSE_CATEGORIES`, `INCOME_CATEGORIES`, `SPECIAL_CATEGORIES` arrays
  - Export `getCategoryById(id: string)` and `getCategoryLabel(id: string)` helpers

- [x] T003 Create SQLAlchemy models in `backend/app/modules/bas/classification_models.py`
  - `ClassificationRequest` model per data-model.md: all fields, relationships to `Tenant`, `XeroConnection`, `BASSession`, `PortalInvitation`, `PracticeUser`
  - `ClientClassification` model per data-model.md: all fields including receipt fields (`receipt_required`, `receipt_flag_source`, `receipt_flag_reason`, `receipt_document_id`), relationships to `ClassificationRequest`, `PortalSession`, `PortalDocument`, `TaxCodeSuggestion`
  - `ClassificationRequestStatus` string constants (DRAFT, SENT, VIEWED, IN_PROGRESS, SUBMITTED, REVIEWING, COMPLETED, CANCELLED, EXPIRED)
  - Add unique constraints and indexes per data-model.md
  - Import both models in `backend/app/modules/bas/__init__.py`

- [x] T004 Create Alembic migration in `backend/alembic/versions/047_spec_047_client_classification.py`
  - Create `classification_requests` table
  - Create `client_classifications` table
  - All indexes, unique constraints, and foreign keys per data-model.md
  - Test: `cd backend && uv run alembic upgrade head` succeeds

- [x] T005 Add new audit event type constants in `backend/app/modules/bas/models.py`
  - Add to `BASAuditEventType`: `CLASSIFICATION_REQUEST_CREATED`, `CLASSIFICATION_REQUEST_SENT`, `CLASSIFICATION_REQUEST_SUBMITTED`, `CLASSIFICATION_REVIEWED`, `CLASSIFICATION_AI_MAPPED`

- [x] T006 Add domain exceptions in `backend/app/modules/bas/exceptions.py`
  - `ClassificationRequestExistsError` — active request already exists for session
  - `ClassificationRequestNotFoundError`
  - `ClassificationNotFoundError`
  - `NoUnresolvedTransactionsError`
  - `NoClientEmailError` — no email on XeroClient and no override provided
  - `ClassificationRequestExpiredError`
  - `InvalidClassificationActionError`

- [x] T007 Create Pydantic schemas in `backend/app/modules/bas/classification_schemas.py`
  - Request schemas: `ClassificationRequestCreate`, `ClassificationResolve`, `ClassificationBulkApprove`, `ClientClassificationSave`
  - Response schemas: `ClassificationRequestResponse`, `ClassificationRequestStatusResponse`, `ClassificationReviewResponse`, `ClassificationReviewItem`, `ClassificationReviewSummary`, `ClientClassificationView`, `ClientTransactionView`, `ClientClassifyPageResponse`
  - Validators: at least one of category/description/is_personal/needs_help required on `ClientClassificationSave`

**Checkpoint**: Models created, migration runs, constants defined. Ready for service layer.

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Wire up portal email sending (existing gap) and create core service

- [x] T008 Wire email sending in portal `InvitationService.create_invitation()` in `backend/app/modules/portal/service.py`
  - After `MagicLinkService.create_invitation()` returns, call `EmailService.send_email()` with `PortalEmailTemplates.portal_invitation()` template
  - Wrap in try/except — email failure should not fail invitation creation (follow pattern from `auth/service.py:1133`)
  - Call `MagicLinkService.mark_invitation_sent()` on success or failure
  - Import `get_email_service` from `notifications/email_service.py` and `PortalEmailTemplates` from `portal/notifications/templates.py`

- [x] T009 Add new email template `transaction_classification_request` in `backend/app/modules/portal/notifications/templates.py`
  - Add method `PortalEmailTemplates.transaction_classification_request()` following existing template pattern
  - Parameters: `business_name`, `practice_name`, `accountant_name`, `portal_url`, `transaction_count`, `expires_in`, `message` (optional)
  - Subject: "{practice_name} needs you to classify {transaction_count} transactions"
  - Body: count of transactions, optional message from accountant, prominent CTA button to magic link, expiry notice
  - Receipt callout: "Some transactions may require a receipt or invoice"

- [x] T010 Create `ClassificationService` scaffold in `backend/app/modules/bas/classification_service.py`
  - Constructor takes `AsyncSession`, creates `BASRepository`
  - Stub methods (implement in later phases): `create_request()`, `get_request_status()`, `cancel_request()`, `get_review()`, `resolve_classification()`, `bulk_approve()`, `map_client_classifications()`, `export_audit_trail()`
  - Add receipt auto-flag helper: `_should_require_receipt(amount, category_id, description)` using rules from `classification_constants.py`

- [x] T011 Create `ClassificationRepository` methods in `backend/app/modules/bas/repository.py`
  - `create_classification_request()` — insert with ON CONFLICT check on session_id unique constraint
  - `get_classification_request_by_session()` — lookup by session_id
  - `get_classification_request_by_id()` — lookup by id with tenant_id filter
  - `create_client_classifications_batch()` — bulk insert classification rows for selected transactions
  - `get_classifications_by_request()` — list all classifications for a request
  - `update_classification()` — save client's category/description/is_personal/needs_help
  - `update_classification_ai_mapping()` — save AI suggestion fields
  - `update_classification_accountant_action()` — save accountant resolve action
  - `update_request_status()` — update status field
  - `count_classified()` — count classifications where `classified_at IS NOT NULL`
  - `get_unprocessed_classifications()` — where `classified_at IS NOT NULL AND ai_mapped_at IS NULL`

**Checkpoint**: Service scaffold, repository, email wiring complete. User story implementation can begin.

---

## Phase 3: User Story 1 — Accountant Requests Client Classification (P1) 🎯 MVP

**Goal**: Accountant clicks "Request Client Input" in BAS prep, system sends magic link to client

**Independent Test**: Create a classification request via API → verify magic link email sent → verify request status is "sent"

- [x] T012 [US1] Implement `ClassificationService.create_request()` in `backend/app/modules/bas/classification_service.py`
  - Accept: `session_id`, `tenant_id`, `user_id`, `message`, `transaction_ids` (optional), `email_override`, `manual_receipt_flags`
  - Validate: session is editable, no existing active request for session
  - Get unresolved transactions from `TaxCodeService.detect_and_generate()` or existing pending suggestions
  - Look up client email from `XeroClient.email` (via connection_id → xero_client), fall back to `email_override`
  - Raise `NoClientEmailError` if neither available
  - Create `ClassificationRequest` record (status: DRAFT)
  - Create `ClientClassification` records for each transaction (denormalized snapshots)
  - Apply auto-receipt-flag rules via `_should_require_receipt()` + apply manual flags from request
  - Create `PortalInvitation` via `MagicLinkService.create_invitation()` with 7-day expiry
  - Send email via `EmailService` with `transaction_classification_request` template
  - Update request status to SENT
  - Create audit event `CLASSIFICATION_REQUEST_CREATED`
  - Return request response

- [x] T013 [US1] Implement `ClassificationService.get_request_status()` in `backend/app/modules/bas/classification_service.py`
  - Return current request for session with status, counts, timestamps

- [x] T014 [US1] Implement `ClassificationService.cancel_request()` in `backend/app/modules/bas/classification_service.py`
  - Set request status to CANCELLED, expire the portal invitation

- [x] T015 [US1] Add accountant-facing API endpoints in `backend/app/modules/bas/router.py`
  - `POST /{connection_id}/bas/sessions/{session_id}/classification/request` — create request (calls T012)
  - `GET /{connection_id}/bas/sessions/{session_id}/classification/request` — get status (calls T013)
  - `POST /{connection_id}/bas/sessions/{session_id}/classification/request/cancel` — cancel (calls T014)
  - All require Clerk auth via `get_current_practice_user`
  - Convert domain exceptions to HTTPException in router

- [x] T016 [US1] Mount new endpoints in `backend/app/main.py`
  - Ensure the new classification routes are accessible under the existing BAS router prefix

- [x] T017 [US1] Create `ClassificationRequestButton` component in `frontend/src/components/bas/ClassificationRequestButton.tsx`
  - Button: "Request Client Input" — shown when unresolved transactions exist
  - On click: show modal with optional message field, email preview (from XeroClient), manual email input if missing
  - Checkbox list of transactions for manual receipt flagging
  - Submit calls `POST .../classification/request`
  - After creation: show status badge (Sent, Viewed, In Progress, Submitted, Completed)

- [x] T018 [US1] Integrate `ClassificationRequestButton` into BAS prep page
  - Find the BAS prep page that shows unresolved transactions (spec 046 UI)
  - Add the button alongside existing "Generate Suggestions" flow
  - Show request status indicator when an active request exists

**Checkpoint**: Accountant can create a classification request. Client receives an email with a magic link. Status is visible in BAS prep.

---

## Phase 4: User Story 2 — Client Classifies Transactions (P1)

**Goal**: Client clicks magic link, sees transactions in plain English, classifies them, submits

**Independent Test**: Click magic link → land on classification page → classify 3 transactions → save progress → submit → verify server has classifications

- [x] T019 [US2] Create client-facing classification router in `backend/app/modules/portal/classification_router.py`
  - `GET /api/v1/client-portal/classify/{request_id}` — returns transactions + categories + progress (per contracts/api.md endpoint 8)
  - `PUT /api/v1/client-portal/classify/{request_id}/transactions/{classification_id}` — save individual classification (endpoint 9)
  - `POST /api/v1/client-portal/classify/{request_id}/submit` — submit all classifications (endpoint 10)
  - `POST /api/v1/client-portal/classify/{request_id}/transactions/{classification_id}/receipt` — upload receipt (endpoint 11)
  - All use `CurrentPortalClient` dependency for auth
  - Validate `request.connection_id == portal_session.connection_id`
  - On first GET: update request status to VIEWED
  - On first PUT: update request status to IN_PROGRESS

- [x] T020 [US2] Implement client-facing service methods in `backend/app/modules/bas/classification_service.py`
  - `get_client_view(request_id, connection_id)` — return transactions with categories, hints, receipt flags, progress. Do NOT expose account_codes, tax types, or Xero IDs to client.
  - `save_classification(classification_id, connection_id, session_id, data)` — save category/description/is_personal/needs_help, set classified_at + classified_by_session
  - `submit_classifications(request_id, connection_id)` — set request submitted_at, update status to SUBMITTED, send notification to accountant, create audit event `CLASSIFICATION_REQUEST_SUBMITTED`
  - `attach_receipt(classification_id, connection_id, document_id)` — link uploaded PortalDocument to classification

- [x] T021 [US2] Mount client classification router in `backend/app/main.py`
  - Mount `classification_router` under `/api/v1/client-portal` prefix
  - Ensure JWT middleware exclusion list includes `/api/v1/client-portal/classify` paths

- [x] T022 [US2] Add `classify.*` methods to portal API client in `frontend/src/lib/api/portal.ts`
  - `classify.getRequest(requestId)` — GET classification request (client view)
  - `classify.saveClassification(requestId, classificationId, data)` — PUT individual classification
  - `classify.submit(requestId)` — POST submit
  - `classify.uploadReceipt(requestId, classificationId, file)` — POST receipt upload

- [x] T023 [US2] Create `TransactionClassifier` component in `frontend/src/components/portal/TransactionClassifier.tsx`
  - Props: transaction data, categories, receipt flag, onSave callback
  - Shows: date, amount, description, receipt flag with reason
  - Category picker: grouped buttons/dropdown for expense/income/special categories
  - Free text input for "Other" category
  - "Personal expense" and "I don't know" as distinct special actions
  - Receipt upload zone (drag-drop or camera) when `receipt_required` is true
  - Auto-saves on selection change (debounced 500ms)
  - Visual indicator: classified (green check) vs unclassified

- [x] T024 [US2] Create client classification page in `frontend/src/app/portal/classify/[requestId]/page.tsx`
  - Uses portal layout (existing `/portal/layout.tsx`)
  - On mount: call `classify.getRequest(requestId)` — fetches transactions + categories
  - Renders: practice name, accountant message, progress bar (X of Y classified)
  - List of `TransactionClassifier` components — one per transaction
  - "Submit" button — enabled when at least 1 transaction classified
  - After submit: thank you screen with summary
  - Mobile-first responsive design — most clients will open on phone
  - Handle expired link gracefully (show message, not error)

**Checkpoint**: Client can open magic link, classify transactions in plain English, attach receipts for flagged items, and submit. Progress saves automatically.

---

## Phase 5: User Story 3 — AI Maps Client Descriptions to Tax Codes (P2)

**Goal**: After client submits, AI translates plain-English descriptions to BAS tax codes

**Independent Test**: Submit 5 classifications → trigger AI mapping → verify `TaxCodeSuggestion` records created with tier `client_classified`

- [x] T025 [US3] Implement `ClassificationService.map_client_classifications()` in `backend/app/modules/bas/classification_service.py`
  - Get all unprocessed classifications for request (classified_at set, ai_mapped_at null)
  - Skip `client_needs_help` items (no AI mapping — flagged for accountant)
  - For `client_is_personal` items: create suggestion with tax_type "BASEXCLUDED", confidence 0.95, tier "client_classified"
  - For categorized items: build enhanced LLM prompt including client category + description + transaction context
  - Call `TaxCodeService.suggest_from_llm()` variant with enhanced prompt context
  - Create `TaxCodeSuggestion` records with `confidence_tier = "client_classified"`, confidence 0.70-0.90 (category selection = higher, free text only = lower)
  - Link suggestion back to `ClientClassification.suggestion_id`
  - Set `ai_suggested_tax_type`, `ai_confidence`, `ai_mapped_at` on each classification
  - Create audit event `CLASSIFICATION_AI_MAPPED`

- [x] T026 [US3] Add enhanced LLM prompt for client-classified transactions in `backend/app/modules/bas/tax_code_service.py`
  - New method `suggest_from_client_input(items_with_client_context)` or extend `suggest_from_llm()` to accept optional client descriptions
  - Prompt includes: "The business owner has classified this transaction as '{category}'" and/or "The business owner described this as: '{description}'"
  - Instruct the LLM to weight the client's input heavily but still validate against transaction amount and account context

**Checkpoint**: AI mapping produces `TaxCodeSuggestion` records that the existing spec 046 review infrastructure can consume.

---

## Phase 6: User Story 4 — Accountant Reviews Client Classifications (P2)

**Goal**: Accountant sees client descriptions + AI mappings, approves or overrides each

**Independent Test**: Open review screen → see all classifications with client input + AI suggestions → approve 3, override 1 → verify suggestions resolved

- [x] T027 [US4] Implement `ClassificationService.get_review()` in `backend/app/modules/bas/classification_service.py`
  - Trigger AI mapping (T025) if not yet done (lazy evaluation on first review access)
  - Return all classifications with: transaction details, client input, AI suggestion, receipt status, needs_attention flag
  - `needs_attention` = true when: confidence < 0.7, client_needs_help, client_is_personal, receipt_required but not attached
  - Return summary counts per contracts/api.md endpoint 4
  - Update request status to REVIEWING

- [x] T028 [US4] Implement `ClassificationService.resolve_classification()` in `backend/app/modules/bas/classification_service.py`
  - Accept: classification_id, tenant_id, user_id, action (approved/overridden/rejected), tax_type (if override), reason
  - For approved: set accountant_action, accountant_user_id, accountant_acted_at; update linked TaxCodeSuggestion via `TaxCodeService.approve_suggestion()`
  - For overridden: same + set accountant_tax_type; call `TaxCodeService.override_suggestion()`
  - For rejected: call `TaxCodeService.reject_suggestion()`
  - Create audit event `CLASSIFICATION_REVIEWED`

- [x] T029 [US4] Implement `ClassificationService.bulk_approve()` in `backend/app/modules/bas/classification_service.py`
  - Accept: request_id, tenant_id, user_id, min_confidence, exclude_personal, exclude_needs_help
  - Approve all qualifying classifications in one pass
  - Return approved/skipped counts

- [x] T030 [US4] Add review API endpoints in `backend/app/modules/bas/router.py`
  - `GET /{connection_id}/bas/sessions/{session_id}/classification/review` — get review data (endpoint 4)
  - `POST /{connection_id}/bas/sessions/{session_id}/classification/{classification_id}/resolve` — approve/override (endpoint 5)
  - `POST /{connection_id}/bas/sessions/{session_id}/classification/bulk-approve` — bulk approve (endpoint 6)

- [ ] T031 [US4] Create `ClassificationReview` component in `frontend/src/components/bas/ClassificationReview.tsx`
  - Table/card view of all classifications with columns: transaction, client said, AI suggests, confidence, receipt, action
  - Color coding: green (high confidence, auto-mappable), amber (needs attention), red (client needs help / personal)
  - Per-row actions: Approve (one-click if confidence high), Override (dropdown of tax codes + reason), Reject
  - Receipt indicator: attached (view link) / missing (warning icon)
  - Bulk approve button with confidence threshold slider
  - Summary bar: X classified, Y approved, Z need attention, receipts: A/B attached
  - "Complete Review" button — marks request as COMPLETED when all classifications resolved

- [ ] T032 [US4] Integrate review screen into BAS prep page
  - When classification request status is SUBMITTED or REVIEWING, show a "Review Client Classifications" button/tab
  - Link to the ClassificationReview component
  - After all classifications resolved: update request status to COMPLETED

**Checkpoint**: Accountant can review all client classifications, approve/override each, and complete the review. Resolved suggestions feed into the existing spec 046 `apply_and_recalculate()` flow.

---

## Phase 7: User Story 5 — Audit Trail (P2)

**Goal**: Every classification has a complete, immutable, ATO-ready audit chain

**Independent Test**: Complete a full flow (request → classify → map → review) → export audit trail → verify all fields populated for every classification

- [x] T033 [US5] Implement `ClassificationService.export_audit_trail()` in `backend/app/modules/bas/classification_service.py`
  - Accept: session_id, tenant_id, format (json/csv)
  - Query all classifications for the session with full audit fields
  - JSON format: array of objects with all FR-17 fields
  - CSV format: one row per classification with headers matching FR-17 fields
  - Include: classified_by (connection_id), classified_at, client_description, client_category, ai_suggested_code, ai_confidence, accountant_action, accountant_user_id, approved_at, final_tax_code, override_reason, receipt_required, receipt_flag_reason, receipt_attached, receipt_document_id

- [x] T034 [US5] Add audit export endpoint in `backend/app/modules/bas/router.py`
  - `GET /{connection_id}/bas/sessions/{session_id}/classification/audit-export` — endpoint 7
  - Query param `format` (json/csv, default json)
  - CSV response with `Content-Type: text/csv` and `Content-Disposition: attachment` headers

- [ ] T035 [US5] Add audit export button to ClassificationReview component
  - "Export Audit Trail" button in the review screen header
  - Downloads CSV when clicked

**Checkpoint**: Complete audit trail exportable per BAS period. Every classification records who said what, when, and what was approved.

---

## Phase 8: User Story 6 — Auto-Flag Receipts (P1)

**Goal**: System automatically flags transactions that need receipts without accountant intervention

**Independent Test**: Create request with transactions of varying amounts and categories → verify correct transactions are auto-flagged → verify client sees receipt indicators

Note: The auto-flag logic is implemented as part of `create_request()` in T012 and displayed in T023/T024. This phase validates and refines the rules.

- [x] T036 [US6] Implement `_should_require_receipt()` helper in `backend/app/modules/bas/classification_service.py`
  - Input: `amount`, `category_id` (nullable — not yet classified), `description`, `account_code`
  - Rule 1: `abs(amount) > 82.50` AND transaction is an expense → flag with reason "GST credit claim over $82.50 — tax invoice required"
  - Rule 2: category in `[computer_it, tools_equipment]` → flag with reason "Capital purchase — evidence required for asset write-off"
  - Rule 3: category is `meals_entertainment` → flag with reason "Entertainment expense — documentation required for FBT"
  - Rule 4: category is `subcontractor` → flag with reason "Subcontractor payment — invoice and ABN required for TPAR"
  - Rule 5: description matches `VAGUE_DESCRIPTION_PATTERNS` → flag with reason "Unclear bank description — receipt needed to verify transaction"
  - Return: `(should_flag: bool, reason: str | None)`

- [x] T037 [US6] Implement re-evaluation of receipt flags after client classification in `backend/app/modules/bas/classification_service.py`
  - When client selects a category (in `save_classification()`), re-evaluate receipt flag rules using the NEW category
  - If category triggers a receipt rule (e.g., client selects "Meals & entertainment"), add/update the flag
  - If client changes from a flagged category to an unflagged one, keep the flag if it was set by another rule (amount) or manual

**Checkpoint**: Receipt flags are automatically applied on request creation AND dynamically updated as client classifies. No extra accountant work.

---

## Phase 9: Polish & Cross-Cutting Concerns

- [ ] T038 [P] Add notification to accountant when client submits in `backend/app/modules/notifications/`
  - In-app notification: "Client {business_name} has submitted their transaction classifications"
  - Email notification using existing `EmailService`

- [ ] T039 [P] Handle expired classification requests
  - Background check (or on-access check): if `expires_at < now()` and status not terminal (COMPLETED/CANCELLED), set status to EXPIRED
  - Show appropriate message on client page if link is expired

- [ ] T040 [P] Add request status to BAS session summary in existing BAS API
  - When fetching BAS session details, include classification request status if one exists
  - Frontend: show status badge on the BAS prep dashboard card

- [ ] T041 Run `cd backend && uv run ruff check . && uv run ruff format .` — fix any lint issues
- [ ] T042 Run `cd frontend && npm run lint && npx tsc --noEmit` — fix any frontend issues

---

## Phase FINAL: PR & Merge

- [ ] T043 Run full validation suite
  - Backend: `cd backend && uv run ruff check . && uv run pytest`
  - Frontend: `cd frontend && npm run lint && npx tsc --noEmit`
  - All checks must pass

- [ ] T044 Push feature branch and create PR
  - Run: `git push -u origin 047-client-transaction-classification`
  - Create PR with summary of changes

- [ ] T045 Address review feedback (if any)

- [ ] T046 Merge PR to main

- [ ] T047 Update ROADMAP.md
  - Mark spec 047 as COMPLETE
  - Update current focus

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 0 (Git)**: Already done
- **Phase 1 (Setup)**: Models, migration, constants — no external dependencies
- **Phase 2 (Foundational)**: Depends on Phase 1 — email wiring, service scaffold, repository
- **Phase 3 (US1)**: Depends on Phase 2 — accountant creates request, email sent
- **Phase 4 (US2)**: Depends on Phase 3 — client needs a request to classify
- **Phase 5 (US3)**: Depends on Phase 4 — AI maps client's classifications
- **Phase 6 (US4)**: Depends on Phase 5 — accountant reviews AI mappings
- **Phase 7 (US5)**: Depends on Phase 6 — audit export needs completed reviews
- **Phase 8 (US6)**: Receipt flag logic is called in Phase 3 (T012) but refined here — can be developed in parallel with Phases 4-5
- **Phase 9 (Polish)**: After core phases complete

### User Story Dependencies

```
US1 (Accountant requests) → US2 (Client classifies) → US3 (AI maps) → US4 (Accountant reviews)
                                                                              ↓
                                                                        US5 (Audit trail)
US6 (Receipt flags) — parallel with US2-US3, used in US1 creation
```

### Within Each Phase

- Models before repository
- Repository before service
- Service before router/endpoints
- Backend before frontend

### Parallel Opportunities

**Phase 1**: T001 + T002 can run in parallel (backend + frontend constants)
**Phase 2**: T008 + T009 can run in parallel (email wiring + template)
**Phase 3-4**: T017 + T018 (frontend) can run in parallel with T019-T021 (backend)
**Phase 9**: T038 + T039 + T040 all independent

---

## Parallel Example: Phase 1

```
# Backend constants and frontend constants can be written simultaneously:
Task T001: "Create category taxonomy constants in backend/app/modules/bas/classification_constants.py"
Task T002: "Create frontend category taxonomy in frontend/src/lib/constants/classification-categories.ts"

# Models and audit events can also be parallel:
Task T003: "Create SQLAlchemy models in backend/app/modules/bas/classification_models.py"
Task T005: "Add new audit event type constants in backend/app/modules/bas/models.py"
```

---

## Implementation Strategy

### MVP First (Phase 1-4 = US1 + US2)

1. Complete Phase 1: Models, migration, constants
2. Complete Phase 2: Email wiring, service scaffold
3. Complete Phase 3: Accountant creates request → email sent
4. Complete Phase 4: Client classifies transactions
5. **STOP and VALIDATE**: Accountant sends request → client classifies → data saved
6. This alone is valuable even without AI mapping — accountant can see raw client descriptions

### Incremental Delivery

1. **MVP**: Phases 1-4 → Accountant sends, client classifies
2. **AI layer**: Phase 5 → AI maps descriptions to tax codes
3. **Review**: Phase 6 → Accountant approves/overrides with full UI
4. **Compliance**: Phase 7 → Audit trail export
5. **Polish**: Phases 8-9 → Receipt refinement, notifications, status badges

### Bootstrap Team Strategy

Given few-hours-per-week constraint:
- **Suren + Asaf**: Phases 1-2 (backend foundation) — 1 session
- **Suren**: Phase 3 backend (create request service) — 1 session
- **Asaf**: Phase 4 backend (client API) — 1 session in parallel
- **Suren**: Phase 4 frontend (client classification page) — 1 session
- **Vik + Unni**: Review category taxonomy (T001) and receipt flag rules (T036) — async
- **Suren**: Phases 5-6 (AI mapping + review) — 2 sessions
- **Asaf**: Phase 7 (audit export) — 1 session in parallel
