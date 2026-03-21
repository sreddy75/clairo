# Implementation Plan: ATO Correspondence Parsing

**Branch**: `027-ato-correspondence-parsing` | **Date**: 2026-01-01 | **Spec**: [spec.md](./spec.md)
**Input**: Feature specification from `/specs/027-ato-correspondence-parsing/spec.md`

## Summary

Parse synced ATO emails using Claude to extract structured data (notice type, due dates, amounts, reference numbers) and automatically match correspondence to clients. This is the intelligence layer that transforms raw email capture into actionable ATOtrack data.

**Technical Approach**:
- Extend `modules/email/` with parsing service
- Use Claude API for structured extraction with confidence scores
- Implement ABN exact matching and fuzzy name matching for clients
- Store embeddings in Qdrant for semantic search
- Create triage queue for low-confidence matches

---

## Technical Context

**Language/Version**: Python 3.12+
**Primary Dependencies**: FastAPI, SQLAlchemy 2.x, Pydantic v2, anthropic SDK, qdrant-client
**Storage**: PostgreSQL 16 + Qdrant (vector store)
**Testing**: pytest, pytest-asyncio
**Target Platform**: AWS ECS/Fargate (Sydney region)
**Project Type**: Web application (backend + frontend)
**Performance Goals**: Parse within 30 seconds, search within 2 seconds
**Constraints**: Tenant data isolation in vector store, 7-year retention
**Scale/Scope**: Up to 1,000 emails/day per tenant

---

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

| Principle | Compliance | Notes |
|-----------|------------|-------|
| **Modular Monolith** | ✅ PASS | Extends `modules/email/` with parsing submodule |
| **Repository Pattern** | ✅ PASS | ATOCorrespondenceRepository |
| **Multi-tenancy (RLS)** | ✅ PASS | All tables + Qdrant collections scoped by tenant |
| **Audit-First** | ✅ PASS | Audit events for parsing, matching, corrections |
| **Type Hints** | ✅ PASS | Pydantic schemas, typed functions |
| **Test-First** | ✅ PASS | Mock Claude API, test parsing accuracy |
| **API Conventions** | ✅ PASS | RESTful endpoints for correspondence |
| **AI Integration Pattern** | ✅ PASS | Structured output, confidence scores, error handling |

**No violations requiring justification.**

---

## Project Structure

### Documentation (this feature)

```text
specs/027-ato-correspondence-parsing/
├── plan.md              # This file
├── research.md          # AI parsing research
├── data-model.md        # Entity definitions
├── quickstart.md        # Developer guide
├── contracts/           # OpenAPI specs
│   └── correspondence-api.yaml
└── tasks.md             # Implementation tasks
```

### Source Code (repository root)

```text
backend/
├── app/
│   └── modules/
│       └── email/
│           ├── parsing/                  # NEW SUBMODULE
│           │   ├── __init__.py
│           │   ├── service.py            # Parsing orchestration
│           │   ├── claude_parser.py      # Claude API integration
│           │   ├── notice_types.py       # Notice type taxonomy
│           │   └── prompts.py            # Parsing prompts
│           │
│           ├── matching/                 # NEW SUBMODULE
│           │   ├── __init__.py
│           │   ├── service.py            # Client matching service
│           │   ├── abn_matcher.py        # Exact ABN matching
│           │   └── fuzzy_matcher.py      # Name fuzzy matching
│           │
│           ├── vector/                   # NEW SUBMODULE
│           │   ├── __init__.py
│           │   ├── service.py            # Qdrant operations
│           │   └── embeddings.py         # Embedding generation
│           │
│           ├── correspondence/           # NEW SUBMODULE
│           │   ├── __init__.py
│           │   ├── models.py             # ATOCorrespondence, etc.
│           │   ├── schemas.py            # Pydantic schemas
│           │   ├── repository.py         # Correspondence repository
│           │   ├── service.py            # Correspondence service
│           │   └── router.py             # API endpoints
│           │
│           └── triage/                   # NEW SUBMODULE
│               ├── __init__.py
│               ├── service.py            # Triage queue service
│               └── router.py             # Triage endpoints
│
└── tests/
    ├── unit/
    │   └── modules/
    │       └── email/
    │           ├── test_claude_parser.py
    │           ├── test_abn_matcher.py
    │           ├── test_fuzzy_matcher.py
    │           └── test_vector_service.py
    └── integration/
        └── api/
            └── test_correspondence.py

frontend/
└── src/
    ├── app/
    │   └── (protected)/
    │       └── ato-inbox/
    │           ├── page.tsx              # Main inbox
    │           ├── [id]/page.tsx         # Correspondence detail
    │           └── triage/page.tsx       # Triage queue
    ├── components/
    │   └── correspondence/
    │       ├── CorrespondenceCard.tsx
    │       ├── NoticeTypeBadge.tsx
    │       ├── ConfidenceIndicator.tsx
    │       ├── ClientMatcher.tsx
    │       └── TriageItem.tsx
    └── lib/
        └── api/
            └── correspondence.ts
```

**Structure Decision**: Creates submodules within `modules/email/` to maintain cohesion with email integration while separating concerns.

---

## Architecture

### Component Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      ATO PARSING ARCHITECTURE                           │
│                                                                         │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    RAW EMAIL (from Spec 026)                       │ │
│  └───────────────────────────────┬───────────────────────────────────┘ │
│                                  │                                      │
│                                  ▼                                      │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    PARSING SERVICE                                 │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │   Claude    │  │  Notice     │  │  Prompt     │               │ │
│  │  │   Parser    │  │  Types      │  │  Templates  │               │ │
│  │  └──────┬──────┘  └─────────────┘  └─────────────┘               │ │
│  │         │                                                          │ │
│  │         ▼                                                          │ │
│  │  ┌─────────────────────────────────────────────────────────┐      │ │
│  │  │  Structured Output                                       │      │ │
│  │  │  - notice_type, due_date, amount, reference             │      │ │
│  │  │  - client_identifier, required_action                    │      │ │
│  │  │  - confidence_score                                      │      │ │
│  │  └──────────────────────────┬──────────────────────────────┘      │ │
│  └─────────────────────────────┼─────────────────────────────────────┘ │
│                                │                                        │
│                                ▼                                        │
│  ┌───────────────────────────────────────────────────────────────────┐ │
│  │                    MATCHING SERVICE                                │ │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐               │ │
│  │  │    ABN      │  │   Fuzzy     │  │  Confidence │               │ │
│  │  │   Matcher   │  │   Matcher   │  │   Scorer    │               │ │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘               │ │
│  │         └────────────────┼────────────────┘                       │ │
│  │                          ▼                                         │ │
│  │  ┌─────────────────────────────────────────────────────────┐      │ │
│  │  │  Match Result                                            │      │ │
│  │  │  - client_id (if matched)                                │      │ │
│  │  │  - match_confidence (0-100)                              │      │ │
│  │  │  - requires_triage (if confidence < 80%)                 │      │ │
│  │  └──────────────────────────┬──────────────────────────────┘      │ │
│  └─────────────────────────────┼─────────────────────────────────────┘ │
│                                │                                        │
│           ┌────────────────────┴────────────────────┐                  │
│           ▼                                          ▼                  │
│  ┌─────────────────────┐                ┌─────────────────────┐        │
│  │    PostgreSQL       │                │     Qdrant          │        │
│  │                     │                │                     │        │
│  │  ATOCorrespondence  │                │  Vector embeddings  │        │
│  │  (structured data)  │                │  (semantic search)  │        │
│  └─────────────────────┘                └─────────────────────┘        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

### Parsing Pipeline

```
PARSING PIPELINE
═══════════════════════════════════════════════════════════════════════════

1. EMAIL ARRIVES (Celery task triggered by email.received event)
   │
   ▼
2. EXTRACT CONTENT
   ├── Get body_text or body_html from RawEmail
   ├── If PDF attachments exist → extract text (PyPDF2/pdfplumber)
   └── Combine into single content block
   │
   ▼
3. CLAUDE PARSING
   ├── Build prompt with content and examples
   ├── Call Claude API with structured output schema
   ├── Parse JSON response
   └── Validate against Pydantic schema
   │
   ▼
4. CLIENT MATCHING
   ├── If ABN found → exact match against clients table
   ├── If name only → fuzzy match using Levenshtein/token matching
   ├── Calculate match confidence (0-100)
   └── If confidence < 80% → mark for triage
   │
   ▼
5. VECTOR EMBEDDING
   ├── Generate embedding for email content
   ├── Store in Qdrant with metadata
   └── Enable semantic search
   │
   ▼
6. STORAGE
   ├── Create ATOCorrespondence record
   ├── Link to RawEmail
   ├── Link to Client (if matched)
   └── Set status = NEW
   │
   ▼
7. EVENTS
   ├── Emit correspondence.parsed event
   ├── If matched → correspondence.matched event
   └── If needs triage → add to triage queue
```

### Entity Relationships

```
┌─────────────────────────────────────────────────────────────────────────┐
│                       ENTITY RELATIONSHIPS                               │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  Tenant                                                                 │
│    │                                                                    │
│    ├──► RawEmail (from Spec 026)                                       │
│    │         │                                                          │
│    │         └──► ATOCorrespondence (1:1)                              │
│    │                   │                                                │
│    │                   ├──► Client (N:1, optional)                     │
│    │                   │                                                │
│    │                   ├──► Task (future, Spec 028)                    │
│    │                   │                                                │
│    │                   └──► Insight (future, Spec 028)                 │
│    │                                                                    │
│    └──► Client                                                         │
│              │                                                          │
│              └──► ATOCorrespondence (1:N)                              │
│                                                                         │
│  Qdrant Collections (per tenant):                                       │
│    ├── ato_correspondence_{tenant_id}                                  │
│    └── Contains: email content embeddings + metadata                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Data Flow

### Parsing Flow

```
1. email.received event fires (from Spec 026)
   │
   ▼
2. Celery task: parse_ato_email(raw_email_id)
   │
   ▼
3. Load RawEmail with body content
   │
   ├──► If has PDF attachments → extract_pdf_text()
   │
   ▼
4. Call Claude API for structured extraction
   │
   ├──► Prompt includes: email content, notice type list, examples
   ├──► Response: JSON with extracted fields + confidence
   │
   ▼
5. Match to client
   │
   ├──► Try ABN match (exact)
   ├──► Fallback to fuzzy name match
   ├──► Calculate overall confidence
   │
   ▼
6. Generate embedding and store in Qdrant
   │
   ▼
7. Create ATOCorrespondence record
   │
   ├──► Link to RawEmail, Client (if matched)
   ├──► Store parsed fields and confidence
   │
   ▼
8. If needs_triage → create TriageItem
   │
   ▼
9. Emit events: correspondence.parsed, correspondence.matched
```

### Search Flow

```
1. User enters search query
   │
   ▼
2. Generate embedding for query
   │
   ▼
3. Search Qdrant collection (tenant-scoped)
   │
   ├──► Filter by: notice_type, date_range, client_id
   ├──► Return top N by vector similarity
   │
   ▼
4. Load full ATOCorrespondence records
   │
   ▼
5. Return ranked results
```

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| AI Model | Claude 3.5 Sonnet | Good balance of accuracy and cost |
| Structured Output | JSON mode | Reliable extraction with schema validation |
| Embedding Model | text-embedding-3-small | Cost-effective, good quality |
| Vector Store | Qdrant | Already in stack, tenant isolation support |
| Fuzzy Matching | rapidfuzz | Fast, accurate Levenshtein implementation |
| PDF Extraction | pdfplumber | Better than PyPDF2 for complex layouts |
| Confidence Threshold | 80% | Balance automation vs. manual review |

---

## Risk Assessment

| Risk | Mitigation |
|------|------------|
| Claude parsing errors | Confidence scores, manual correction, improve prompts |
| High AI costs | Batch processing, caching, model selection |
| Fuzzy match false positives | Require manual confirmation below threshold |
| Qdrant tenant isolation | Collection-per-tenant, strict access control |
| PDF extraction failures | Fallback to OCR, store original for retry |
| Rate limiting | Queue management, exponential backoff |

---

## Dependencies

### Internal Dependencies

| Dependency | Status | Notes |
|------------|--------|-------|
| Spec 026 (Email Integration) | Required | Provides RawEmail entities |
| Clients module | Required | For ABN/name matching |
| Qdrant setup | Required | Vector storage |
| Claude API setup | Required | AI parsing |
| Spec 028 (ATOtrack) | Dependent | Consumes parsed correspondence |

### External Dependencies

| Dependency | Version | Purpose |
|------------|---------|---------|
| anthropic | 0.35+ | Claude API client |
| qdrant-client | 1.7+ | Vector storage |
| rapidfuzz | 3.0+ | Fuzzy string matching |
| pdfplumber | 0.10+ | PDF text extraction |
| openai | 1.0+ | Embeddings (if using OpenAI) |

---

## Phase References

- **Phase 0**: See [research.md](./research.md) for AI parsing research
- **Phase 1**: See [data-model.md](./data-model.md) for entity definitions
- **Phase 1**: See [contracts/correspondence-api.yaml](./contracts/correspondence-api.yaml) for API specs
- **Phase 1**: See [quickstart.md](./quickstart.md) for developer guide
