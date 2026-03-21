# Feature Specification: AI Interaction Capture & Learning

**Feature Branch**: `029-ai-interaction-capture-learning`
**Created**: 2026-01-01
**Status**: Draft
**Phase**: E.6 (AI Intelligence Flywheel)

## Overview

Implement a comprehensive AI interaction capture and learning system that creates a data flywheel - every AI interaction improves the product. This includes capturing query/response metadata, user feedback, outcome tracking, pattern analysis, knowledge gap identification, and fine-tuning dataset curation.

**Why This Matters**:
- Every interaction becomes training data for model improvement
- Pattern analysis reveals feature opportunities and knowledge gaps
- Feedback loops enable continuous AI quality improvement
- Creates an unreplicable data moat over time
- Year 3 target: 1M+ interactions with industry-leading AI quality

**The Intelligence Flywheel**:
```
Accountants Ask → AI Responds → We Capture Everything
       ↑                              ↓
Better Outcomes ← Model Improvement ← Pattern Analysis
```

**Disruption Level**: Low (additive instrumentation to existing AI systems)

---

## User Scenarios & Testing

### User Story 1 - Interaction Capture (Priority: P1)

As a platform operator, I want every AI interaction captured with full context so that we have training data for improvement.

**Why this priority**: Foundation for all learning - no capture, no flywheel.

**Independent Test**: Ask AI a question → verify AIInteraction record created with 40+ fields.

**Acceptance Scenarios**:

1. **Given** a user asks the AI a question, **When** the response is returned, **Then** an AIInteraction record is created with query, response, context, and timing.

2. **Given** the interaction is in a BAS prep session, **When** captured, **Then** session_type, client context, and days_to_deadline are recorded.

3. **Given** the AI used RAG sources, **When** captured, **Then** sources_count, sources_avg_score, and source_types are recorded.

---

### User Story 2 - Query Auto-Classification (Priority: P1)

As a platform operator, I want queries automatically classified by category so that we can analyze patterns by topic.

**Why this priority**: Classification enables meaningful pattern analysis.

**Independent Test**: Ask GST question → verify category="COMPLIANCE", subcategory="GST".

**Acceptance Scenarios**:

1. **Given** a user asks about GST credits, **When** captured, **Then** category is auto-set to "COMPLIANCE" and subcategory to "GST".

2. **Given** a user asks about cash flow projections, **When** captured, **Then** category is auto-set to "STRATEGY".

3. **Given** a user asks about data discrepancies, **When** captured, **Then** category is auto-set to "DATA_QUALITY".

4. **Given** a user asks about task reminders, **When** captured, **Then** category is auto-set to "WORKFLOW".

---

### User Story 3 - Feedback Collection (Priority: P1)

As an accountant, I want to rate AI responses with thumbs up/down so that the AI can learn from my feedback.

**Why this priority**: Explicit feedback is the clearest quality signal.

**Independent Test**: Click thumbs down → verify feedback_rating recorded on interaction.

**Acceptance Scenarios**:

1. **Given** I receive an AI response, **When** I view it, **Then** I see thumbs up/down buttons.

2. **Given** I click thumbs up, **When** feedback is submitted, **Then** the AIInteraction record is updated with feedback_rating=5.

3. **Given** I click thumbs down, **When** I optionally add a comment, **Then** feedback_comment is also recorded.

---

### User Story 4 - Outcome Tracking (Priority: P1)

As a platform operator, I want to track what users do after AI responses so that we can measure AI effectiveness.

**Why this priority**: Actions speak louder than ratings.

**Independent Test**: AI suggests insight → user creates it → verify action_type and time_to_action recorded.

**Acceptance Scenarios**:

1. **Given** an AI response suggests creating an insight, **When** the user creates one within 5 minutes, **Then** action_type="created_insight" and time_to_action_seconds are recorded.

2. **Given** an AI response, **When** the user immediately asks a follow-up, **Then** had_follow_up=true and follow_up_interaction_id are recorded.

3. **Given** an AI response, **When** the user copies the text, **Then** copied_response=true is recorded.

---

### User Story 5 - Pattern Analysis (Priority: P2)

As an admin, I want to see query patterns and trends so that I can identify feature opportunities.

**Why this priority**: Patterns reveal what users really need.

**Independent Test**: Daily job runs → QueryPattern records created with occurrence counts.

**Acceptance Scenarios**:

1. **Given** similar queries appear 50+ times, **When** the daily pattern job runs, **Then** a QueryPattern record is created with canonical_query and occurrence_count.

2. **Given** I view the admin dashboard, **When** I check patterns, **Then** I see top query categories and emerging trends.

3. **Given** a pattern like "compare to last year" appears frequently, **When** analyzed, **Then** suggested_feature is populated.

---

### User Story 6 - Knowledge Gap Identification (Priority: P2)

As an admin, I want to see where AI performs poorly so that we can improve those areas.

**Why this priority**: Fix weaknesses to improve overall satisfaction.

**Independent Test**: Topic with avg satisfaction < 3.5 → KnowledgeGap record created.

**Acceptance Scenarios**:

1. **Given** queries about "FBT electric vehicles" have avg satisfaction 2.8/5, **When** weekly analysis runs, **Then** a KnowledgeGap record is created with priority_score.

2. **Given** I view knowledge gaps, **When** I check the list, **Then** I see sample queries and suggested resolution type.

3. **Given** we add a KB article for a gap, **When** I mark it resolved, **Then** status changes and we track improvement.

---

### User Story 7 - Fine-Tuning Candidate Identification (Priority: P2)

As an admin, I want high-quality interactions auto-identified so that we can curate training data.

**Why this priority**: Automation scales the curation process.

**Independent Test**: Interaction with positive feedback + action taken → marked as candidate.

**Acceptance Scenarios**:

1. **Given** an interaction has thumbs up + action taken + no follow-up, **When** daily job runs, **Then** a FineTuningCandidate record is created with quality_score.

2. **Given** I view candidates, **When** I filter by category, **Then** I see balanced distribution across COMPLIANCE, STRATEGY, etc.

3. **Given** a candidate exists, **When** I review it, **Then** I can approve, reject, or edit the response.

---

### User Story 8 - Training Data Curation (Priority: P2)

As an admin, I want to curate and export training datasets so that we can fine-tune our models.

**Why this priority**: Curated data enables model improvement.

**Independent Test**: Approve 100 examples → export JSONL → verify format correct.

**Acceptance Scenarios**:

1. **Given** I approve a candidate, **When** I optionally edit the response, **Then** a FineTuningExample is created with system_prompt, user_message, ideal_response.

2. **Given** 1000+ examples are approved, **When** I export a dataset, **Then** train.jsonl and eval.jsonl are generated with 90/10 split.

3. **Given** I export a dataset, **When** complete, **Then** a FineTuningDataset record tracks version, stats, and category distribution.

---

### User Story 9 - Privacy Controls (Priority: P1)

As a tenant admin, I want to control whether our data is used for training so that we maintain trust.

**Why this priority**: Privacy is non-negotiable for compliance-focused customers.

**Independent Test**: Opt out of training → verify interactions excluded from fine-tuning.

**Acceptance Scenarios**:

1. **Given** I access AI settings, **When** I view options, **Then** I see toggles for training contribution, pattern analysis, benchmarking.

2. **Given** I disable "contribute to training", **When** our team uses AI, **Then** consent_training=false on all interactions.

3. **Given** consent_training=false, **When** fine-tuning candidates are identified, **Then** our interactions are excluded.

---

### User Story 10 - Admin Intelligence Dashboard (Priority: P2)

As an admin, I want a dashboard showing AI learning metrics so that I can monitor the flywheel.

**Why this priority**: Visibility drives action and demonstrates value.

**Independent Test**: Open dashboard → see interaction count, satisfaction trends, knowledge gaps.

**Acceptance Scenarios**:

1. **Given** I open the AI Intelligence dashboard, **When** it loads, **Then** I see total interactions, satisfaction score, and week-over-week trends.

2. **Given** I view the dashboard, **When** I check query categories, **Then** I see distribution chart (COMPLIANCE 42%, STRATEGY 22%, etc.).

3. **Given** I view the dashboard, **When** I check fine-tuning, **Then** I see candidate count, approved examples, and next dataset status.

---

### Edge Cases

- What if the user refreshes before feedback?
  → Track time_reading_ms via beforeunload, infer engagement

- What if the same query is asked repeatedly?
  → Deduplicate via query_hash, increment pattern occurrence

- What if model response is empty or error?
  → Still capture with response_text=null, note error in metadata

- What if tenant opts out mid-conversation?
  → Apply preference to new interactions only, don't retroactively change

- What if fine-tuning example contains PII?
  → Anonymization pipeline strips PII before training use

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST capture all AI interactions with 40+ metadata fields
- **FR-002**: System MUST auto-classify queries into categories (>90% accuracy)
- **FR-003**: System MUST provide thumbs up/down feedback UI on all AI responses
- **FR-004**: System MUST track implicit signals (follow-ups, actions, copy events)
- **FR-005**: System MUST identify query patterns via daily clustering job
- **FR-006**: System MUST identify knowledge gaps from low-satisfaction topics
- **FR-007**: System MUST auto-identify fine-tuning candidates from quality signals
- **FR-008**: System MUST support human curation of training examples
- **FR-009**: System MUST export category-balanced JSONL training datasets
- **FR-010**: System MUST provide tenant opt-out from training data
- **FR-011**: System MUST anonymize PII before training use
- **FR-012**: System MUST provide admin dashboard for intelligence metrics

### Key Entities

- **AIInteraction**: Core capture with query, response, outcome, feedback (40+ fields)
- **QueryPattern**: Aggregated patterns with occurrence counts, satisfaction
- **KnowledgeGap**: Low-satisfaction topics needing attention
- **FineTuningCandidate**: Auto-identified high-quality interactions
- **FineTuningExample**: Human-curated, approved training examples
- **FineTuningDataset**: Versioned JSONL exports for model training
- **TenantAISettings**: Privacy preferences per tenant

### Non-Functional Requirements

- **NFR-001**: Interaction capture MUST add <50ms latency to AI responses
- **NFR-002**: Pattern analysis job MUST complete within 10 minutes
- **NFR-003**: Admin dashboard MUST load within 3 seconds
- **NFR-004**: Raw interaction logs MUST be retained for 2 years (configurable)
- **NFR-005**: JSONL export MUST handle 10,000+ examples within 5 minutes
- **NFR-006**: Query embedding generation MUST be async (not blocking response)

---

## Auditing & Compliance Checklist

### Audit Events Required

- [x] **Interaction Events**: Yes - all AI interactions logged
- [x] **Feedback Events**: Yes - user ratings captured
- [x] **Curation Events**: Yes - example approval/rejection
- [x] **Export Events**: Yes - dataset generation
- [x] **Privacy Events**: Yes - consent changes

### Audit Implementation Requirements

| Event Type | Trigger | Data Captured | Retention | Sensitive Data |
|------------|---------|---------------|-----------|----------------|
| `ai.interaction.captured` | AI response returned | interaction_id, category, latency | 7 years | PII in raw_log |
| `ai.feedback.submitted` | User rates response | interaction_id, rating, comment | 7 years | None |
| `ai.pattern.identified` | Daily job | pattern_id, occurrence_count | 7 years | None |
| `ai.gap.identified` | Weekly job | gap_id, topic, priority | 7 years | None |
| `ai.example.approved` | Admin curates | example_id, curator_id, edited | 7 years | None |
| `ai.dataset.exported` | Dataset generated | version, example_count | 7 years | None |
| `ai.settings.changed` | Tenant updates prefs | tenant_id, setting, old/new | 7 years | None |

---

## Success Criteria

### Measurable Outcomes

- **SC-001**: 100% of AI interactions captured with full context
- **SC-002**: Query auto-classification accuracy >90%
- **SC-003**: >20% of users provide feedback (up/down) on responses
- **SC-004**: Weekly pattern analysis identifying 10+ distinct patterns
- **SC-005**: Knowledge gaps resolved within 2 weeks of identification
- **SC-006**: 1000+ curated examples ready for first fine-tuning

---

## Technical Notes (for Plan phase)

### Capture Architecture

```python
# Capture happens in AI middleware, after response generation
async def capture_interaction(
    query: str,
    response: str,
    context: SessionContext,
    rag_results: list[RAGResult] | None,
    model: str,
    latency_ms: int,
) -> AIInteraction:
    # Auto-classify query
    category, subcategory = await classify_query(query)

    # Generate embedding async (don't block response)
    background_tasks.add_task(generate_query_embedding, interaction_id)

    return AIInteraction(
        query_text=query,
        query_hash=sha256(query),
        category=category,
        subcategory=subcategory,
        response_text=response,
        response_latency_ms=latency_ms,
        model_version=model,
        # ... 30+ more fields from context
    )
```

### Query Classification Prompt

```python
CLASSIFY_PROMPT = """
Classify this accountant query into exactly one category:
- COMPLIANCE: Tax rules, ATO requirements, BAS/GST/PAYG questions
- STRATEGY: Business advice, cash flow, growth, forecasting
- DATA_QUALITY: Reconciliation issues, missing data, discrepancies
- WORKFLOW: Tasks, reminders, notifications, process questions

Also identify subcategory if applicable (GST, PAYG, SUPER, etc.)

Query: {query}

Return JSON: {"category": "...", "subcategory": "..." or null}
"""
```

### Fine-Tuning Quality Score

```python
def calculate_quality_score(interaction: AIInteraction) -> float:
    """Calculate 0-1 quality score from signals."""
    score = 0.0

    # Explicit feedback (40% weight)
    if interaction.feedback_rating == 5:
        score += 0.4
    elif interaction.feedback_rating == 1:
        return 0.0  # Negative feedback = not a candidate

    # Action taken (30% weight)
    if interaction.action_type is not None:
        score += 0.3

    # No follow-up needed (20% weight)
    if interaction.had_follow_up is False:
        score += 0.2

    # High confidence (10% weight)
    if interaction.confidence_score and interaction.confidence_score > 0.8:
        score += 0.1

    return score
```

---

## Dependencies

- **Existing AI modules**: Required - chat, insights, agents to instrument
- **Qdrant**: Required - vector storage for query embeddings
- **S3/MinIO**: Required - raw log and dataset storage
- **Redis**: Required - real-time metrics counters
- **Celery**: Required - background jobs for pattern analysis
