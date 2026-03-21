# Implementation Tasks: AI Interaction Capture & Learning

**Feature**: 029-ai-interaction-capture-learning
**Branch**: `029-ai-interaction-capture-learning`
**Total Tasks**: 82
**Estimated Phases**: 12

---

## Overview

This task list implements the AI intelligence flywheel - capturing every AI interaction, analyzing patterns, identifying knowledge gaps, and curating fine-tuning datasets.

### User Stories (from spec.md)

| Story | Priority | Description |
|-------|----------|-------------|
| US1 | P1 | Interaction Capture |
| US2 | P1 | Query Auto-Classification |
| US3 | P1 | Feedback Collection |
| US4 | P1 | Outcome Tracking |
| US5 | P2 | Pattern Analysis |
| US6 | P2 | Knowledge Gap Identification |
| US7 | P2 | Fine-Tuning Candidate Identification |
| US8 | P2 | Training Data Curation |
| US9 | P1 | Privacy Controls |
| US10 | P2 | Admin Intelligence Dashboard |

### Dependencies

```
US1 (Capture) ──► US2 (Classification) ──┐
                                          ├──► US5 (Patterns) ──► US6 (Gaps)
US3 (Feedback) ──► US4 (Outcomes) ───────┘
                                          │
                                          └──► US7 (Candidates) ──► US8 (Curation)

US9 (Privacy) - Independent, affects capture
US10 (Dashboard) - Depends on all analysis
```

---

## Phase 1: Setup (6 tasks)

**Goal**: Create ai_learning module structure and database tables

- [ ] T001 Create ai_learning module directory in backend/app/modules/ai_learning/
- [ ] T002 Create ai_learning __init__.py with module exports in backend/app/modules/ai_learning/__init__.py
- [ ] T003 Create models.py with all 7 entity models in backend/app/modules/ai_learning/models.py
- [ ] T004 [P] Create Alembic migration for ai_learning tables in backend/alembic/versions/
- [ ] T005 Create test directories in backend/tests/unit/modules/ai_learning/ and backend/tests/integration/api/
- [ ] T006 Register ai_learning router in main.py in backend/app/main.py

---

## Phase 2: Foundational - Shared Components (6 tasks)

**Goal**: Build shared infrastructure for capture and analysis

- [ ] T007 Create enums.py with QueryCategory, SessionType, GapStatus, CandidateStatus in backend/app/modules/ai_learning/enums.py
- [ ] T008 Create exceptions.py with InteractionNotFoundError, CandidateAlreadyExistsError in backend/app/modules/ai_learning/exceptions.py
- [ ] T009 Create base schemas.py for request/response schemas in backend/app/modules/ai_learning/schemas.py
- [ ] T010 Create repository.py with AIInteractionRepository base in backend/app/modules/ai_learning/repository.py
- [ ] T011 [P] Create Qdrant collection config for ai_queries in backend/app/modules/ai_learning/capture/embeddings.py
- [ ] T012 [P] Create S3 bucket config for raw logs in backend/app/modules/ai_learning/storage.py

---

## Phase 3: User Story 9 - Privacy Controls (6 tasks)

**Goal**: Tenant consent settings before capture begins
**Independent Test**: Disable training consent → verify interactions excluded from candidates

- [ ] T013 [US9] Create TenantAISettings model in backend/app/modules/ai_learning/models.py
- [ ] T014 [US9] Create TenantAISettingsRepository in backend/app/modules/ai_learning/privacy/settings.py
- [ ] T015 [US9] Create GET/PATCH /settings/ai endpoints in backend/app/modules/ai_learning/router.py
- [ ] T016 [US9] Create AISettings component in frontend in frontend/src/app/(protected)/settings/ai/page.tsx
- [ ] T017 [P] [US9] Write unit tests for settings in backend/tests/unit/modules/ai_learning/test_settings.py
- [ ] T018 [US9] Write integration tests for settings API in backend/tests/integration/api/test_ai_learning.py

---

## Phase 4: User Story 1 - Interaction Capture (10 tasks)

**Goal**: Capture all AI interactions with 40+ metadata fields
**Independent Test**: Ask AI question → verify AIInteraction record created with full context

### Capture Middleware

- [ ] T019 [US1] Create AIInteractionMiddleware class in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T020 [US1] Implement _extract_query() for request parsing in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T021 [US1] Implement _extract_response() for response parsing in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T022 [US1] Implement _capture_interaction() with all metadata fields in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T023 [US1] Register middleware in FastAPI app in backend/app/main.py

### Storage Integration

- [ ] T024 [US1] Implement raw log upload to S3 in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T025 [US1] Implement Redis metrics recording in backend/app/modules/ai_learning/analysis/metrics.py
- [ ] T026 [P] [US1] Write unit tests for middleware in backend/tests/unit/modules/ai_learning/test_middleware.py

### Embedding Generation

- [ ] T027 [US1] Create QueryEmbedder class with OpenAI integration in backend/app/modules/ai_learning/capture/embeddings.py
- [ ] T028 [US1] Create Celery task for async embedding generation in backend/app/tasks/ai_learning/embeddings.py

---

## Phase 5: User Story 2 - Query Auto-Classification (6 tasks)

**Goal**: Auto-classify queries into categories with >90% accuracy
**Independent Test**: Ask GST question → verify category="COMPLIANCE", subcategory="GST"

- [ ] T029 [US2] Create QueryClassifier class with Claude Haiku in backend/app/modules/ai_learning/capture/classifier.py
- [ ] T030 [US2] Define CLASSIFY_PROMPT with examples in backend/app/modules/ai_learning/capture/classifier.py
- [ ] T031 [US2] Integrate classifier into capture middleware in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T032 [US2] Add classification caching for repeated queries in backend/app/modules/ai_learning/capture/classifier.py
- [ ] T033 [P] [US2] Write unit tests for classifier in backend/tests/unit/modules/ai_learning/test_classifier.py
- [ ] T034 [US2] Create classification accuracy validation script in backend/scripts/validate_classification.py

---

## Phase 6: User Story 3 - Feedback Collection (6 tasks)

**Goal**: Thumbs up/down feedback UI on all AI responses
**Independent Test**: Click thumbs down → verify feedback_rating recorded

- [ ] T035 [US3] Create feedback submission endpoint POST /ai/feedback/{interaction_id} in backend/app/modules/ai_learning/router.py
- [ ] T036 [US3] Implement FeedbackService for updating interactions in backend/app/modules/ai_learning/service.py
- [ ] T037 [US3] Create FeedbackButtons component in frontend/src/components/ai/FeedbackButtons.tsx
- [ ] T038 [US3] Integrate FeedbackButtons into Chat, Insights, MagicZone UI in frontend/src/components/
- [ ] T039 [P] [US3] Write unit tests for feedback service in backend/tests/unit/modules/ai_learning/test_feedback.py
- [ ] T040 [US3] Write integration tests for feedback API in backend/tests/integration/api/test_ai_learning.py

---

## Phase 7: User Story 4 - Outcome Tracking (6 tasks)

**Goal**: Track implicit signals (follow-ups, actions, copy events)
**Independent Test**: AI suggests insight → user creates it → verify action_type recorded

- [ ] T041 [US4] Implement follow-up detection in capture middleware in backend/app/modules/ai_learning/capture/middleware.py
- [ ] T042 [US4] Create action correlation service in backend/app/modules/ai_learning/service.py
- [ ] T043 [US4] Add copy event tracking via frontend hook in frontend/src/hooks/useInteractionTracking.ts
- [ ] T044 [US4] Add time_reading_ms tracking via beforeunload in frontend/src/hooks/useInteractionTracking.ts
- [ ] T045 [P] [US4] Write unit tests for outcome tracking in backend/tests/unit/modules/ai_learning/test_outcomes.py
- [ ] T046 [US4] Write integration tests for outcome correlation in backend/tests/integration/api/test_ai_learning.py

---

## Phase 8: User Story 5 - Pattern Analysis (7 tasks)

**Goal**: Identify query patterns via clustering
**Independent Test**: Daily job runs → QueryPattern records created with occurrence counts

- [ ] T047 [US5] Create PatternClusterer class in backend/app/modules/ai_learning/analysis/patterns.py
- [ ] T048 [US5] Implement agglomerative clustering with Qdrant embeddings in backend/app/modules/ai_learning/analysis/patterns.py
- [ ] T049 [US5] Create QueryPatternRepository in backend/app/modules/ai_learning/repository.py
- [ ] T050 [US5] Create daily pattern analysis Celery task in backend/app/tasks/ai_learning/pattern_analysis.py
- [ ] T051 [US5] Schedule pattern_analysis task in Celery beat in backend/app/tasks/celery_config.py
- [ ] T052 [P] [US5] Write unit tests for pattern clustering in backend/tests/unit/modules/ai_learning/test_patterns.py
- [ ] T053 [US5] Write integration tests for pattern job in backend/tests/integration/tasks/test_pattern_analysis.py

---

## Phase 9: User Story 6 - Knowledge Gap Identification (6 tasks)

**Goal**: Identify low-satisfaction topics needing attention
**Independent Test**: Topic with avg satisfaction < 3.5 → KnowledgeGap record created

- [ ] T054 [US6] Create calculate_priority_score() function in backend/app/modules/ai_learning/analysis/gaps.py
- [ ] T055 [US6] Create KnowledgeGapRepository in backend/app/modules/ai_learning/repository.py
- [ ] T056 [US6] Create weekly gap detection Celery task in backend/app/tasks/ai_learning/gap_detection.py
- [ ] T057 [US6] Schedule gap_detection task in Celery beat in backend/app/tasks/celery_config.py
- [ ] T058 [P] [US6] Write unit tests for gap detection in backend/tests/unit/modules/ai_learning/test_gaps.py
- [ ] T059 [US6] Write integration tests for gap job in backend/tests/integration/tasks/test_gap_detection.py

---

## Phase 10: User Story 7 - Fine-Tuning Candidate Identification (6 tasks)

**Goal**: Auto-identify high-quality interactions for training
**Independent Test**: Interaction with positive feedback + action taken → marked as candidate

- [ ] T060 [US7] Create calculate_quality_score() function in backend/app/modules/ai_learning/finetuning/candidates.py
- [ ] T061 [US7] Create FineTuningCandidateRepository in backend/app/modules/ai_learning/repository.py
- [ ] T062 [US7] Create daily candidate scoring Celery task in backend/app/tasks/ai_learning/candidate_scoring.py
- [ ] T063 [US7] Schedule candidate_scoring task in Celery beat in backend/app/tasks/celery_config.py
- [ ] T064 [P] [US7] Write unit tests for quality scoring in backend/tests/unit/modules/ai_learning/test_quality_score.py
- [ ] T065 [US7] Write integration tests for candidate job in backend/tests/integration/tasks/test_candidate_scoring.py

---

## Phase 11: User Story 8 - Training Data Curation (8 tasks)

**Goal**: Human curation and JSONL export of training datasets
**Independent Test**: Approve 100 examples → export JSONL → verify format correct

### Curation Service

- [ ] T066 [US8] Create FineTuningExampleRepository in backend/app/modules/ai_learning/repository.py
- [ ] T067 [US8] Create Anonymizer class for PII removal in backend/app/modules/ai_learning/finetuning/anonymizer.py
- [ ] T068 [US8] Create curation service with approve/reject logic in backend/app/modules/ai_learning/finetuning/curation.py
- [ ] T069 [P] [US8] Write unit tests for anonymizer in backend/tests/unit/modules/ai_learning/test_anonymizer.py

### JSONL Export

- [ ] T070 [US8] Create JSONLExporter class in backend/app/modules/ai_learning/finetuning/exporter.py
- [ ] T071 [US8] Create FineTuningDatasetRepository in backend/app/modules/ai_learning/repository.py
- [ ] T072 [US8] Create export dataset endpoint POST /finetuning/datasets in backend/app/modules/ai_learning/router.py
- [ ] T073 [US8] Write integration tests for JSONL export in backend/tests/integration/api/test_ai_learning.py

---

## Phase 12: User Story 10 - Admin Intelligence Dashboard (8 tasks)

**Goal**: Admin dashboard for AI learning metrics
**Independent Test**: Open dashboard → see interaction count, satisfaction trends

### Backend API

- [ ] T074 [US10] Create DashboardService with aggregation logic in backend/app/modules/ai_learning/dashboard.py
- [ ] T075 [US10] Create admin router with dashboard endpoints in backend/app/modules/ai_learning/router.py
- [ ] T076 [US10] Create pattern/gap/candidate list endpoints in backend/app/modules/ai_learning/router.py
- [ ] T077 [P] [US10] Write integration tests for admin endpoints in backend/tests/integration/api/test_ai_learning.py

### Frontend Dashboard

- [ ] T078 [US10] Create AI Intelligence dashboard page in frontend/src/app/(protected)/admin/ai-intelligence/page.tsx
- [ ] T079 [US10] Create MetricsCards component in frontend/src/components/admin/ai-intelligence/MetricsCards.tsx
- [ ] T080 [US10] Create CategoryChart component in frontend/src/components/admin/ai-intelligence/CategoryChart.tsx
- [ ] T081 [US10] Create CurationQueue component in frontend/src/components/admin/ai-intelligence/CurationQueue.tsx

---

## Phase 13: Polish & Cross-Cutting (1 task)

**Goal**: Final validation and documentation

- [ ] T082 Update API documentation and validate all endpoints in specs/029-ai-interaction-capture-learning/contracts/

---

## Parallel Execution Guide

### Maximum Parallelism by Phase

| Phase | Parallel Groups |
|-------|-----------------|
| Phase 1 | T001 → T002-T06 |
| Phase 2 | T007-T09, (T10+T11+T12) |
| Phase 3 | T013-T15, T16, T17+T18 |
| Phase 4 | T019-T23 → T24-T26 → T27+T28 |
| Phase 5 | T029-T32, T33+T34 |
| Phase 6 | T035-T36, T37-T38, T39+T40 |
| Phase 7 | T041-T42, T43+T44, T45+T46 |
| Phase 8 | T047-T51, T52+T53 |
| Phase 9 | T054-T57, T58+T59 |
| Phase 10 | T060-T63, T64+T65 |
| Phase 11 | T066-T68+T69, T70-T73 |
| Phase 12 | T074-T77, T78-T81 |

### Independent Work Streams

```
Stream A (Capture): Phase 4 → Phase 5 → Phase 6 → Phase 7
Stream B (Analysis): Phase 8 → Phase 9 (after Stream A)
Stream C (Fine-Tuning): Phase 10 → Phase 11 (after Stream A)
Stream D (Dashboard): Phase 12 (after all analysis streams)
Stream E (Privacy): Phase 3 (independent, early)
```

---

## MVP Scope

**Minimum Viable Product**: User Stories 1, 2, 3, 9 (Phases 1-6)

| Phase | Tasks | Description |
|-------|-------|-------------|
| 1 | T001-T006 | Setup |
| 2 | T007-T012 | Foundational |
| 3 | T013-T018 | Privacy Controls |
| 4 | T019-T028 | Interaction Capture |
| 5 | T029-T034 | Classification |
| 6 | T035-T040 | Feedback |

**MVP Task Count**: 40 tasks

**Post-MVP**:
- Phase 7: Outcome Tracking (T041-T046)
- Phase 8: Pattern Analysis (T047-T053)
- Phase 9: Knowledge Gaps (T054-T059)
- Phase 10: Candidates (T060-T065)
- Phase 11: Curation & Export (T066-T073)
- Phase 12: Dashboard (T074-T081)
- Phase 13: Polish (T082)

---

## Validation Checklist

- [ ] All 82 tasks follow checklist format
- [ ] Each user story phase is independently testable
- [ ] Dependencies are correctly sequenced
- [ ] Parallel opportunities identified
- [ ] MVP scope defined (40 tasks)
- [ ] File paths specified for all implementation tasks
