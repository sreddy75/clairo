# Tasks: ATO Correspondence Parsing

**Input**: Design documents from `/specs/027-ato-correspondence-parsing/`
**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md, contracts/

**Tests**: Test tasks included for AI parsing accuracy and client matching.

**Organization**: Tasks are grouped by user story to enable independent implementation and testing.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Include exact file paths in descriptions

---

## Phase 0: Git Setup (REQUIRED)

**Purpose**: Create feature branch before any implementation

- [ ] T000 Create feature branch from main
  - Run: `git checkout main && git pull origin main`
  - Run: `git checkout -b feature/027-ato-correspondence-parsing`
  - Verify: You are now on the feature branch

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Module structure and dependencies

- [ ] T001 Create parsing submodule structure in backend/app/modules/email/parsing/
  - Create __init__.py, service.py, claude_parser.py, notice_types.py, prompts.py
- [ ] T002 [P] Create matching submodule structure in backend/app/modules/email/matching/
  - Create __init__.py, service.py, abn_matcher.py, fuzzy_matcher.py
- [ ] T003 [P] Create vector submodule structure in backend/app/modules/email/vector/
  - Create __init__.py, service.py, embeddings.py
- [ ] T004 [P] Create correspondence submodule structure in backend/app/modules/email/correspondence/
  - Create __init__.py, models.py, schemas.py, repository.py, service.py, router.py
- [ ] T005 [P] Create triage submodule structure in backend/app/modules/email/triage/
  - Create __init__.py, service.py, router.py
- [ ] T006 Add dependencies to backend/pyproject.toml
  - Add: anthropic, qdrant-client, rapidfuzz, pdfplumber, openai
  - Run: `uv sync`
- [ ] T007 [P] Add environment variables to backend/app/config.py
  - Add: ANTHROPIC_API_KEY (existing)
  - Add: OPENAI_API_KEY, QDRANT_HOST, QDRANT_PORT, QDRANT_API_KEY
  - Add: PARSING_MODEL, EMBEDDING_MODEL, MATCH_CONFIDENCE_THRESHOLD

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core models and infrastructure that MUST be complete before ANY user story

**CRITICAL**: No user story work can begin until this phase is complete

- [ ] T008 Create ATONoticeType enum in backend/app/modules/email/parsing/notice_types.py
  - All notice types from data-model.md
  - NOTICE_TYPE_METADATA dict with urgency and category
- [ ] T009 [P] Create CorrespondenceStatus and MatchType enums in backend/app/modules/email/correspondence/models.py
- [ ] T010 Create ATOCorrespondence model in backend/app/modules/email/correspondence/models.py
  - All fields from data-model.md
  - Relationships to tenant, raw_email, client
- [ ] T011 [P] Create TriageItem model in backend/app/modules/email/correspondence/models.py
  - All fields from data-model.md
  - Relationship to correspondence
- [ ] T012 [P] Create ParsingJob model in backend/app/modules/email/correspondence/models.py
  - Track batch parsing jobs
- [ ] T013 [P] Create CorrespondenceCorrection model in backend/app/modules/email/correspondence/models.py
  - Track manual corrections for audit
- [ ] T014 Create Alembic migration for correspondence tables
  - Run: `alembic revision --autogenerate -m "Add ATO correspondence tables"`
  - Include: ato_correspondence, triage_items, parsing_jobs, correspondence_corrections
  - Add indexes from data-model.md
  - Enable RLS
- [ ] T015 Create Pydantic schemas in backend/app/modules/email/correspondence/schemas.py
  - CorrespondenceSummary, CorrespondenceDetail, CorrespondenceUpdate
  - TriageItem, TriageListResponse
  - SearchRequest, SearchResponse, SearchResult
  - CorrespondenceStats, CorrectionRequest
- [ ] T016 Create CorrespondenceRepository in backend/app/modules/email/correspondence/repository.py
  - CRUD operations
  - list_by_tenant() with filters
  - get_by_client(), get_overdue()
  - update_vector_id(), update_status()
- [ ] T017 [P] Create TriageRepository in backend/app/modules/email/triage/repository.py
  - CRUD for triage items
  - get_pending_by_tenant()
  - resolve_item()

**Checkpoint**: Foundation ready - user story implementation can now begin

---

## Phase 3: User Story 1 - Automatic Email Parsing (Priority: P1)

**Goal**: Parse synced ATO emails using Claude to extract structured data

**Independent Test**: New ATO email syncs → parsed data appears with notice type, due date, and summary

### Tests for User Story 1

- [ ] T018 [P] [US1] Unit test for ClaudeParser in backend/tests/unit/modules/email/test_claude_parser.py
  - Test parsing penalty notice
  - Test parsing activity statement reminder
  - Test handling missing fields
  - Test JSON parsing error handling
- [ ] T019 [P] [US1] Unit test for notice type classification in backend/tests/unit/modules/email/test_notice_types.py
  - Test all notice type metadata
  - Test urgency levels

### Implementation for User Story 1

- [ ] T020 [US1] Create parsing prompt template in backend/app/modules/email/parsing/prompts.py
  - Main parsing prompt with examples
  - Few-shot examples for each notice type
- [ ] T021 [US1] Implement ClaudeParser in backend/app/modules/email/parsing/claude_parser.py
  - ClientIdentifier and ParsedEmail models
  - parse() method calling Claude API
  - _build_prompt() method
  - Error handling for invalid JSON
- [ ] T022 [US1] Create fallback parser in backend/app/modules/email/parsing/fallback_parser.py
  - Regex-based extraction for when AI fails
  - Extract ABN, dates, amounts
  - Return low confidence score
- [ ] T023 [US1] Create PDF text extraction in backend/app/modules/email/parsing/pdf_extractor.py
  - extract_pdf_text() using pdfplumber
  - OCR fallback for scanned PDFs
- [ ] T024 [US1] Create Celery task for parsing in backend/app/modules/email/parsing/tasks.py
  - parse_new_email(raw_email_id) task
  - Trigger on email.received event
  - Retry with exponential backoff
- [ ] T025 [US1] Wire up email.received event to trigger parsing
  - Add event handler in email module
  - Queue parsing task on new email

**Checkpoint**: Emails are automatically parsed with Claude

---

## Phase 4: User Story 2 - Notice Type Classification (Priority: P1)

**Goal**: Classify emails into notice types for filtering and prioritization

**Independent Test**: View ATO inbox → emails are grouped/filterable by notice type

### Implementation for User Story 2

- [ ] T026 [US2] Add notice type filter to CorrespondenceRepository
  - list_by_tenant(notice_type=...) filter
- [ ] T027 [US2] Create notice type statistics in CorrespondenceService
  - get_stats() with by_notice_type breakdown
- [ ] T028 [P] [US2] Create NoticeTypeBadge component in frontend/src/components/correspondence/NoticeTypeBadge.tsx
  - Color-coded badge per notice type
  - Urgency indicator
- [ ] T029 [US2] Add notice type filter to frontend inbox
  - Filter dropdown in frontend/src/app/(protected)/ato-inbox/page.tsx

**Checkpoint**: Notice types displayed and filterable

---

## Phase 5: User Story 3 - Client Matching (Priority: P1)

**Goal**: Automatically match correspondence to clients by ABN or fuzzy name

**Independent Test**: Email with ABN → automatically matched to correct client

### Tests for User Story 3

- [ ] T030 [P] [US3] Unit test for ABN matching in backend/tests/unit/modules/email/test_abn_matcher.py
  - Test exact ABN match
  - Test normalized ABN (with/without spaces)
  - Test historical ABN lookup
- [ ] T031 [P] [US3] Unit test for fuzzy matching in backend/tests/unit/modules/email/test_fuzzy_matcher.py
  - Test high confidence match (>80%)
  - Test low confidence match (<80%)
  - Test no match found

### Implementation for User Story 3

- [ ] T032 [US3] Implement ABN matcher in backend/app/modules/email/matching/abn_matcher.py
  - normalize_abn() function
  - is_valid_abn() validation
  - match_by_abn() with exact lookup
- [ ] T033 [US3] Implement fuzzy matcher in backend/app/modules/email/matching/fuzzy_matcher.py
  - match_by_name() using rapidfuzz
  - token_set_ratio scorer
  - Confidence threshold handling
- [ ] T034 [US3] Create ClientMatchingService in backend/app/modules/email/matching/service.py
  - MatchResult model
  - match() orchestration method
  - Try ABN → TFN → name fallback
- [ ] T035 [US3] Integrate matching into parsing pipeline
  - Update ParsingService to call matcher
  - Store match_type and match_confidence

**Checkpoint**: Clients automatically matched by ABN or name

---

## Phase 6: User Story 4 - Triage Queue (Priority: P1)

**Goal**: Surface unmatched correspondence for manual assignment

**Independent Test**: View triage queue → assign unmatched email to correct client

### Implementation for User Story 4

- [ ] T036 [US4] Create TriageService in backend/app/modules/email/triage/service.py
  - create_triage_item() when match < threshold
  - assign_client() for manual assignment
  - ignore_item() for irrelevant emails
- [ ] T037 [US4] Create triage router in backend/app/modules/email/triage/router.py
  - GET /correspondence/triage - list pending items
  - POST /correspondence/triage/{id}/assign
  - POST /correspondence/triage/{id}/ignore
- [ ] T038 [P] [US4] Create TriageItem component in frontend/src/components/correspondence/TriageItem.tsx
  - Display extracted identifier
  - Show suggested client with confidence
  - Client selector dropdown
- [ ] T039 [US4] Create triage page in frontend/src/app/(protected)/ato-inbox/triage/page.tsx
  - List pending triage items
  - Assign and ignore actions

**Checkpoint**: Triage queue functional for manual assignment

---

## Phase 7: User Story 5 - Confidence Scores (Priority: P2)

**Goal**: Display parsing confidence scores for review prioritization

**Independent Test**: View parsed email → see confidence percentage for extracted fields

### Implementation for User Story 5

- [ ] T040 [US5] Add confidence fields to correspondence detail view
  - parsing_confidence display
  - match_confidence display
- [ ] T041 [P] [US5] Create ConfidenceIndicator component in frontend/src/components/correspondence/ConfidenceIndicator.tsx
  - Visual bar/percentage
  - Color coding (green/yellow/red)
- [ ] T042 [US5] Add "low confidence" filter to correspondence list
  - Filter items with confidence < 80%

**Checkpoint**: Confidence scores visible and filterable

---

## Phase 8: User Story 6 - Semantic Search (Priority: P2)

**Goal**: Search correspondence by meaning, not just keywords

**Independent Test**: Search "penalty notices last quarter" → relevant results appear

### Tests for User Story 6

- [ ] T043 [P] [US6] Unit test for VectorService in backend/tests/unit/modules/email/test_vector_service.py
  - Test store() creates point
  - Test search() returns results
  - Test tenant isolation

### Implementation for User Story 6

- [ ] T044 [US6] Implement VectorService in backend/app/modules/email/vector/service.py
  - ensure_collection() per tenant
  - store() with embeddings
  - search() with filters
- [ ] T045 [US6] Implement embedding generation in backend/app/modules/email/vector/embeddings.py
  - generate_embedding() using OpenAI
  - Batch embedding for multiple texts
- [ ] T046 [US6] Integrate vector storage into parsing pipeline
  - Store embedding after parsing
  - Update vector_id on correspondence
- [ ] T047 [US6] Create search endpoint in backend/app/modules/email/correspondence/router.py
  - POST /correspondence/search
  - Accept query and filters
  - Return ranked results
- [ ] T048 [P] [US6] Create search UI in frontend/src/app/(protected)/ato-inbox/page.tsx
  - Search input box
  - Results display with relevance score

**Checkpoint**: Semantic search returns relevant results

---

## Phase 9: User Story 7 - Attachment Extraction (Priority: P2)

**Goal**: Parse PDF attachments for structured data

**Independent Test**: Email with PDF notice → PDF content is parsed and structured

### Implementation for User Story 7

- [ ] T049 [US7] Enhance parsing pipeline for attachments
  - Check for PDF attachments on RawEmail
  - Extract text using pdf_extractor
  - Include in parsing content
- [ ] T050 [US7] Handle large attachments
  - Skip attachments > 10MB
  - Log warning for oversized files
- [ ] T051 [US7] Add attachment indicator to correspondence list
  - Show attachment count/icon

**Checkpoint**: PDF attachments parsed and included

---

## Phase 10: Correspondence UI

**Goal**: Full correspondence inbox and detail views

### Implementation

- [ ] T052 Create correspondence router in backend/app/modules/email/correspondence/router.py
  - GET /correspondence - list with filters
  - GET /correspondence/{id} - detail view
  - PATCH /correspondence/{id} - update status
  - POST /correspondence/{id}/assign-client
  - POST /correspondence/{id}/correct
  - POST /correspondence/{id}/resolve
- [ ] T053 Create CorrespondenceService in backend/app/modules/email/correspondence/service.py
  - list_correspondence() with pagination
  - get_correspondence() with detail
  - assign_client(), correct_field(), resolve()
- [ ] T054 [P] Create frontend API client in frontend/src/lib/api/correspondence.ts
  - listCorrespondence(), getCorrespondence()
  - assignClient(), correctField(), resolve()
  - search()
- [ ] T055 Create ATO inbox page in frontend/src/app/(protected)/ato-inbox/page.tsx
  - List correspondence with filters
  - Notice type, status, client filters
  - Overdue and due soon indicators
- [ ] T056 [P] Create CorrespondenceCard component in frontend/src/components/correspondence/CorrespondenceCard.tsx
  - Notice type badge
  - Client name, due date, amount
  - Status indicator
- [ ] T057 Create correspondence detail page in frontend/src/app/(protected)/ato-inbox/[id]/page.tsx
  - Full parsed data display
  - Original email preview
  - Correct field actions
  - Assign client action
- [ ] T058 [P] Create ClientMatcher component in frontend/src/components/correspondence/ClientMatcher.tsx
  - Client search/select
  - Show current match info

**Checkpoint**: Full inbox UI operational

---

## Phase 11: Statistics & Dashboard

**Goal**: Provide overview statistics for correspondence

### Implementation

- [ ] T059 Create statistics endpoint in backend/app/modules/email/correspondence/router.py
  - GET /correspondence/stats
  - By status, by notice type, overdue counts
- [ ] T060 [P] Add correspondence stats to frontend dashboard
  - Overdue count
  - Due this week
  - Triage pending

**Checkpoint**: Statistics visible on dashboard

---

## Phase 12: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [ ] T061 [P] Add audit events for correspondence operations
  - correspondence.parsed, correspondence.matched
  - correspondence.triaged, correspondence.corrected
- [ ] T062 [P] Add rate limiting to parsing
  - Limit concurrent Claude API calls
  - Queue management for batch processing
- [ ] T063 [P] Add parsing cost tracking
  - Track tokens used per tenant
  - Store in parsing job record
- [ ] T064 Create manual correction tracking
  - Store corrections for audit
  - Potential for prompt improvement
- [ ] T065 [P] Run quickstart.md validation
  - Verify all code snippets work
  - Test parsing with real ATO emails
- [ ] T066 Code review and cleanup
  - Consistent error handling
  - Add docstrings
  - Remove debug logging

---

## Phase FINAL: PR & Merge (REQUIRED)

**Purpose**: Create pull request and merge to main

- [ ] TFINAL-1 Ensure all tests pass
  - Run: `uv run pytest backend/tests/unit/modules/email/ -v`
  - Run: `uv run pytest backend/tests/integration/api/test_correspondence*.py -v`
  - All tests must pass before PR

- [ ] TFINAL-2 Run linting and type checking
  - Run: `uv run ruff check backend/app/modules/email/`
  - Run: `uv run mypy backend/app/modules/email/`
  - Run: `npm run lint` in frontend
  - Fix any issues

- [ ] TFINAL-3 Push feature branch and create PR
  - Run: `git push -u origin feature/027-ato-correspondence-parsing`
  - Run: `gh pr create --title "Spec 027: ATO Correspondence Parsing" --body "..."`
  - Include summary of changes in PR description

- [ ] TFINAL-4 Address review feedback (if any)
  - Make requested changes
  - Push additional commits

- [ ] TFINAL-5 Merge PR to main
  - Squash merge after approval
  - Delete feature branch after merge

- [ ] TFINAL-6 Update ROADMAP.md
  - Mark spec 027 as COMPLETE
  - Update current focus to next spec (028)

---

## Dependencies & Execution Order

### Phase Dependencies

- **Git Setup (Phase 0)**: MUST be done first
- **Setup (Phase 1)**: Depends on Phase 0
- **Foundational (Phase 2)**: Depends on Phase 1 - BLOCKS all user stories
- **User Stories (Phases 3-9)**: All depend on Phase 2 completion
  - US1 (Parsing): Foundation for all
  - US2 (Notice Types): Depends on US1
  - US3 (Client Matching): Depends on US1
  - US4 (Triage): Depends on US3
  - US5 (Confidence): Depends on US1
  - US6 (Search): Depends on US1
  - US7 (Attachments): Depends on US1
- **Correspondence UI (Phase 10)**: Depends on US1-US4
- **Statistics (Phase 11)**: Depends on Phase 10
- **Polish (Phase 12)**: Depends on all user stories

### User Story Dependencies

```
US1 (Parsing) ──┬── US2 (Notice Types)
                ├── US3 (Client Matching) ── US4 (Triage)
                ├── US5 (Confidence)
                ├── US6 (Search)
                └── US7 (Attachments)
```

### Parallel Opportunities

**Phase 1 (Setup):**
```
T001 (parsing/) ─┬─ T002 (matching/)
                 ├─ T003 (vector/)    } All in parallel
                 ├─ T004 (correspondence/)
                 └─ T005 (triage/)
```

**Phase 2 (Foundational):**
```
T010 (ATOCorrespondence) ─┬─ T011 (TriageItem)
                          ├─ T012 (ParsingJob)    } In parallel
                          └─ T013 (Correction)
```

**Phase 3 (Parsing Tests):**
```
T018 (parser tests) ─┬─ T019 (notice type tests)  } In parallel
```

---

## Implementation Strategy

### MVP First (Parsing + Matching)

1. Complete Phase 1: Setup
2. Complete Phase 2: Foundational
3. Complete Phase 3: User Story 1 (Parsing)
4. Complete Phase 5: User Story 3 (Client Matching)
5. **STOP and VALIDATE**: Emails parse and match to clients
6. Deploy/demo - this is the core intelligence layer

### Incremental Delivery

1. Setup + Foundational → Foundation ready
2. Add Parsing (US1) → Test → AI extracts structured data
3. Add Notice Types (US2) → Test → Classification working
4. Add Client Matching (US3) → Test → Auto-matching operational
5. Add Triage (US4) → Test → Manual assignment available
6. Add Search (US6) → Test → Semantic search working
7. Add UI (Phase 10) → Test → Full inbox experience

---

## Summary

| Phase | Tasks | Focus |
|-------|-------|-------|
| 0 | 1 | Git setup |
| 1 | 7 | Module structure |
| 2 | 10 | Models, repos, schemas |
| 3 | 8 | Email Parsing (P1) |
| 4 | 4 | Notice Classification (P1) |
| 5 | 6 | Client Matching (P1) |
| 6 | 4 | Triage Queue (P1) |
| 7 | 3 | Confidence Scores (P2) |
| 8 | 6 | Semantic Search (P2) |
| 9 | 3 | Attachment Extraction (P2) |
| 10 | 7 | Correspondence UI |
| 11 | 2 | Statistics |
| 12 | 6 | Polish |
| FINAL | 6 | PR & Merge |

**Total Tasks**: 73
**P1 Stories**: 4 (Parsing, Notice Types, Client Matching, Triage)
**P2 Stories**: 3 (Confidence, Search, Attachments)

---

## Notes

- [P] tasks = different files, no dependencies
- [Story] label maps task to specific user story
- Claude API key required for parsing
- OpenAI API key required for embeddings
- Qdrant must be running for vector storage
- Parsing triggered by email.received event (from Spec 026)
- All parsed data scoped by tenant_id
