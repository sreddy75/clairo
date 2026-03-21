# Implementation Plan: AI Interaction Capture & Learning

**Branch**: `029-ai-interaction-capture-learning` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/029-ai-interaction-capture-learning/spec.md`

## Summary

Implement a comprehensive AI learning system that captures every interaction, analyzes patterns, identifies knowledge gaps, and curates fine-tuning datasets. This creates a data flywheel where more usage leads to smarter AI.

**Technical Approach**:
- Create new `ai_learning` module for capture and analysis
- Instrument existing AI endpoints with capture middleware
- Build admin dashboard for intelligence metrics
- Implement 4-stage fine-tuning pipeline (Capture → Auto-filter → Curate → Export)

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, Celery, Anthropic SDK
**Storage**: PostgreSQL 16, Qdrant, S3/MinIO, Redis
**Testing**: pytest, pytest-asyncio
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Capture <50ms overhead, dashboard <3s, JSONL export <5min
**Constraints**: Must not slow down AI response times
**Scale/Scope**: Handle 100K+ interactions, 10K+ training examples

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | New `ai_learning` module |
| **Repository Pattern** | ✅ PASS | Dedicated repositories for all entities |
| **Multi-tenancy (RLS)** | ✅ PASS | All tables have tenant_id |
| **Audit-First** | ✅ PASS | All capture and curation events audited |
| **Type Hints** | ✅ PASS | Pydantic schemas throughout |
| **Test-First** | ✅ PASS | Test classification, scoring, export |
| **API Conventions** | ✅ PASS | RESTful admin endpoints |
| **Privacy** | ✅ PASS | Consent controls, anonymization |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/029-ai-interaction-capture-learning/
├── plan.md              # This file
├── research.md          # Learning system research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── ai-learning-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── ai_learning/                 # NEW MODULE
│           ├── __init__.py
│           ├── models.py                # All 7 entity models
│           ├── schemas.py               # Request/response schemas
│           ├── repository.py            # Database operations
│           ├── service.py               # Business logic
│           ├── router.py                # Admin API endpoints
│           │
│           ├── capture/                 # Interaction capture
│           │   ├── __init__.py
│           │   ├── middleware.py        # FastAPI middleware
│           │   ├── classifier.py        # Query auto-classification
│           │   └── embeddings.py        # Async embedding generation
│           │
│           ├── analysis/                # Pattern analysis
│           │   ├── __init__.py
│           │   ├── patterns.py          # Query pattern clustering
│           │   ├── gaps.py              # Knowledge gap detection
│           │   └── metrics.py           # Real-time counters
│           │
│           ├── finetuning/              # Training data pipeline
│           │   ├── __init__.py
│           │   ├── candidates.py        # Auto-filter candidates
│           │   ├── curation.py          # Human curation
│           │   ├── anonymizer.py        # PII removal
│           │   └── exporter.py          # JSONL generation
│           │
│           └── privacy/                 # Consent management
│               ├── __init__.py
│               └── settings.py          # Tenant preferences
│
├── tasks/
│   └── ai_learning/
│       ├── pattern_analysis.py          # Daily pattern job
│       ├── gap_detection.py             # Weekly gap analysis
│       └── candidate_scoring.py         # Daily candidate job
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── ai_learning/
    │           ├── test_classifier.py
    │           ├── test_quality_score.py
    │           ├── test_anonymizer.py
    │           └── test_exporter.py
    └── integration/
        └── api/
            └── test_ai_learning.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── admin/
    │           └── ai-intelligence/
    │               ├── page.tsx         # Intelligence dashboard
    │               ├── patterns/page.tsx
    │               ├── gaps/page.tsx
    │               └── finetuning/page.tsx
    ├── components/
    │   ├── ai/
    │   │   └── FeedbackButtons.tsx      # Thumbs up/down
    │   └── admin/
    │       └── ai-intelligence/
    │           ├── MetricsCards.tsx
    │           ├── CategoryChart.tsx
    │           ├── PatternTable.tsx
    │           ├── GapList.tsx
    │           └── CurationQueue.tsx
    └── lib/
        └── api/
            └── ai-learning.ts
```

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                    AI LEARNING ARCHITECTURE                              │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    EXISTING AI ENDPOINTS                           │ │
│  │   Chat API │ Insight API │ Magic Zone │ BAS Prep AI               │ │
│  └─────────────────────────────┬─────────────────────────────────────┘ │
│                                │                                        │
│                                ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    CAPTURE MIDDLEWARE                              │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │   Query     │  │  Response   │  │   Context   │               │ │
│  │  │  Classifier │  │  Capture    │  │  Enrichment │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         │                │                │                        │ │
│  │         └────────────────┼────────────────┘                        │ │
│  │                          ▼                                          │ │
│  │  ┌─────────────────────────────────────────────────────────┐      │ │
│  │  │                 AIInteraction Record                     │      │ │
│  │  │  40+ fields: query, response, context, outcome, privacy │      │ │
│  │  └─────────────────────────────────────────────────────────┘      │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                │                                        │
│         ┌──────────────────────┼──────────────────────┐                │
│         ▼                      ▼                      ▼                │
│  ┌─────────────┐       ┌─────────────┐       ┌─────────────┐          │
│  │ PostgreSQL  │       │   Qdrant    │       │  S3/MinIO   │          │
│  │ Structured  │       │  Embeddings │       │  Raw Logs   │          │
│  └─────────────┘       └─────────────┘       └─────────────┘          │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    ANALYSIS PIPELINE (Celery)                      │ │
│  │                                                                    │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │   Pattern   │  │  Knowledge  │  │  Candidate  │               │ │
│  │  │  Clustering │  │    Gaps     │  │   Scoring   │               │ │
│  │  │   (Daily)   │  │  (Weekly)   │  │   (Daily)   │               │ │
│  │  └─────────────┘  └─────────────┘  └─────────────┘               │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    FINE-TUNING PIPELINE                            │ │
│  │                                                                    │ │
│  │  Candidates ──► Curation UI ──► Examples ──► JSONL Export         │ │
│  │  (auto)         (human)         (approved)   (versioned)          │ │
│  └───────────────────────────────────────────────────────────────────┘ │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Capture Flow

```
INTERACTION CAPTURE FLOW
═══════════════════════════════════════════════════════════════════════════

1. USER SENDS QUERY
   │
   ▼
2. CAPTURE MIDDLEWARE (before AI processing)
   ├── Extract session context (type, client, deadline)
   ├── Generate query hash for deduplication
   └── Record start timestamp
   │
   ▼
3. AI PROCESSING (existing pipeline)
   ├── RAG retrieval (if applicable)
   ├── Agent invocation (if applicable)
   └── Response generation
   │
   ▼
4. CAPTURE MIDDLEWARE (after AI processing)
   ├── Calculate latency
   ├── Extract RAG metrics (sources, scores)
   ├── Auto-classify query (async Claude call)
   ├── Create AIInteraction record
   ├── Queue embedding generation (background)
   └── Upload raw log to S3 (background)
   │
   ▼
5. RESPONSE RETURNED TO USER

OUTCOME TRACKING (async)
═══════════════════════════════════════════════════════════════════════════

- Feedback: User clicks thumbs up/down → update interaction
- Follow-up: Next query within 5 min → link as follow_up_interaction_id
- Action: Task/insight created → link action_type + entity_id
- Copy: Text copied to clipboard → set copied_response=true
```

### Analysis Pipeline

```
PATTERN ANALYSIS (Daily Job)
═══════════════════════════════════════════════════════════════════════════

1. FETCH recent interactions (last 7 days)
   │
   ▼
2. CLUSTER by query embedding similarity
   ├── Use Qdrant for nearest neighbor search
   └── Group similar queries (cosine > 0.85)
   │
   ▼
3. AGGREGATE per cluster
   ├── Canonical query (most representative)
   ├── Occurrence count
   ├── Average satisfaction score
   ├── Follow-up rate
   │
   ▼
4. CREATE/UPDATE QueryPattern records
   │
   ▼
5. IDENTIFY opportunities
   ├── High frequency + feature request → suggested_feature
   └── High frequency + KB topic → suggested_kb_article


KNOWLEDGE GAP DETECTION (Weekly Job)
═══════════════════════════════════════════════════════════════════════════

1. QUERY interactions with low satisfaction (<3.5)
   │
   ▼
2. GROUP BY topic (category + subcategory)
   │
   ▼
3. CALCULATE priority score
   └── weight(volume) × weight(severity) × weight(recency)
   │
   ▼
4. CREATE KnowledgeGap records
   └── Sample queries for context
```

### Fine-Tuning Pipeline

```
4-STAGE FINE-TUNING PIPELINE
═══════════════════════════════════════════════════════════════════════════

STAGE 1: CAPTURE (Automatic)
─────────────────────────────────────────────────────────────────────────
Every AI interaction → AIInteraction record with full context

STAGE 2: AUTO-FILTER (Daily Job)
─────────────────────────────────────────────────────────────────────────
Quality signals:
  ✓ Positive feedback (thumbs up)
  ✓ Action taken (insight/task created)
  ✓ No follow-up needed (clarity achieved)
  ✓ High confidence score

Calculate quality_score → Create FineTuningCandidate if score > 0.6

STAGE 3: HUMAN CURATION (Admin UI)
─────────────────────────────────────────────────────────────────────────
Admin reviews candidates:
  - View original query + response
  - Edit response if needed
  - Rate quality (1-5)
  - Approve → FineTuningExample created
  - Reject → Candidate marked REJECTED

STAGE 4: JSONL EXPORT (On Demand)
─────────────────────────────────────────────────────────────────────────
Generate training dataset:
  - Anonymize PII in approved examples
  - Balance by category (equal representation)
  - Split 90/10 train/eval
  - Export as JSONL to S3
  - Create FineTuningDataset record
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Capture Approach | Middleware | Minimal changes to existing AI endpoints |
| Classification | Claude 3.5 Haiku | Fast, cheap, accurate for simple classification |
| Embedding Model | text-embedding-3-small | Good quality, low cost for query similarity |
| Clustering | Qdrant | Already in stack, efficient nearest neighbor |
| Raw Log Storage | S3/MinIO | Cost-effective for large JSON blobs |
| Training Format | JSONL | Industry standard for fine-tuning |
| Privacy | Opt-out model | Most tenants contribute, privacy-conscious can opt out |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Capture latency | Async for embeddings, S3 upload, classification |
| Storage costs | S3 lifecycle policies, configurable retention |
| PII in training data | Anonymization pipeline before export |
| Classification accuracy | Regular validation, human override option |
| Pattern false positives | Minimum occurrence threshold (50+) |
| Curation bottleneck | Auto-filtering reduces volume by 95% |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Chat module | Required | Instrument for capture |
| Insights module | Required | Instrument for capture |
| Agents module | Required | Instrument for capture |
| Qdrant setup | Required | Already configured |
| S3/MinIO setup | Required | Already configured |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| anthropic | 0.35+ | Classification, fine-tuning API |
| openai | 1.0+ | Embedding generation |
| qdrant-client | 1.7+ | Vector storage and search |
| boto3 | 1.34+ | S3 operations |
| scikit-learn | 1.4+ | Clustering utilities |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for learning system research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/ai-learning-api.yaml](./contracts/ai-learning-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
