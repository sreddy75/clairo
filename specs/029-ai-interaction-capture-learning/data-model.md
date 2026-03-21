# Data Model: AI Interaction Capture & Learning

**Spec**: 029-ai-interaction-capture-learning
**Date**: 2026-01-01

---

## Entity Relationship Diagram

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         DATA MODEL OVERVIEW                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│  ┌─────────────────┐                    ┌─────────────────┐            │
│  │ TenantAISettings│───────────────────▶│     Tenant      │            │
│  │                 │        1:1         │   (existing)    │            │
│  └─────────────────┘                    └─────────────────┘            │
│                                                  │                      │
│                                                  │ 1:N                  │
│                                                  ▼                      │
│  ┌─────────────────────────────────────────────────────────────────┐   │
│  │                       AIInteraction                              │   │
│  │  (40+ fields: query, response, context, outcome, privacy)       │   │
│  └─────────────────────────────────────────────────────────────────┘   │
│           │                    │                    │                   │
│           │ 1:1               │ N:1               │ 1:1                │
│           ▼                    ▼                    ▼                   │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐        │
│  │FineTuningCandidate│ │  QueryPattern   │  │  (follow-up)    │        │
│  └────────┬─────────┘  │  (aggregated)   │  │  AIInteraction  │        │
│           │            └─────────────────┘  └─────────────────┘        │
│           │ 1:1                                                         │
│           ▼                                                             │
│  ┌─────────────────┐                    ┌─────────────────┐            │
│  │FineTuningExample│───────────────────▶│FineTuningDataset│            │
│  │   (curated)     │        N:1         │   (versioned)   │            │
│  └─────────────────┘                    └─────────────────┘            │
│                                                                         │
│  ┌─────────────────┐                                                   │
│  │  KnowledgeGap   │  (standalone, from aggregation)                   │
│  └─────────────────┘                                                   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 1. AIInteraction

The core entity capturing every AI interaction with comprehensive metadata.

```python
from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, Text, Integer, Float, Boolean, ForeignKey, Index
from sqlalchemy.dialects.postgresql import JSONB, ARRAY
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class QueryCategory(str, Enum):
    """Auto-classified query categories."""
    COMPLIANCE = "COMPLIANCE"
    STRATEGY = "STRATEGY"
    DATA_QUALITY = "DATA_QUALITY"
    WORKFLOW = "WORKFLOW"


class SessionType(str, Enum):
    """Type of AI session."""
    CHAT = "CHAT"
    BAS_PREP = "BAS_PREP"
    INSIGHT_REVIEW = "INSIGHT_REVIEW"
    MAGIC_ZONE = "MAGIC_ZONE"
    CLIENT_PORTAL = "CLIENT_PORTAL"


class QueryIntent(str, Enum):
    """Detected query intent."""
    QUESTION = "QUESTION"
    COMMAND = "COMMAND"
    CLARIFICATION = "CLARIFICATION"
    CONFIRMATION = "CONFIRMATION"


class AIInteraction(Base):
    """Comprehensive AI interaction capture with 40+ metadata fields."""
    __tablename__ = "ai_interactions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenants.id"), index=True)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), index=True)
    client_id: Mapped[UUID | None] = mapped_column(ForeignKey("clients.id"), index=True)
    conversation_id: Mapped[UUID | None] = mapped_column(index=True)

    # === QUERY CONTEXT ===
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    query_hash: Mapped[str] = mapped_column(String(64), index=True)  # SHA-256 for dedup
    query_tokens: Mapped[int] = mapped_column(Integer)
    query_embedding_id: Mapped[str | None] = mapped_column(String(100))  # Qdrant point ID

    # Auto-classification
    category: Mapped[str | None] = mapped_column(String(50), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50), index=True)
    intent: Mapped[str | None] = mapped_column(String(50))
    complexity_score: Mapped[float | None] = mapped_column(Float)

    # Session context
    session_type: Mapped[str] = mapped_column(String(50), index=True)
    session_id: Mapped[UUID | None] = mapped_column(index=True)
    queries_in_session: Mapped[int] = mapped_column(Integer, default=1)
    previous_interaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_interactions.id"))

    # Client context (denormalized for analysis)
    client_revenue_band: Mapped[str | None] = mapped_column(String(50))
    client_industry: Mapped[str | None] = mapped_column(String(100))
    client_complexity_score: Mapped[float | None] = mapped_column(Float)

    # Timing context
    days_to_bas_deadline: Mapped[int | None] = mapped_column(Integer)
    is_eofy_period: Mapped[bool] = mapped_column(Boolean, default=False)
    hour_of_day: Mapped[int | None] = mapped_column(Integer)
    day_of_week: Mapped[int | None] = mapped_column(Integer)

    # === RESPONSE CONTEXT ===
    response_text: Mapped[str | None] = mapped_column(Text)
    response_tokens: Mapped[int | None] = mapped_column(Integer)
    response_latency_ms: Mapped[int] = mapped_column(Integer)
    model_version: Mapped[str] = mapped_column(String(100))

    # RAG quality
    sources_count: Mapped[int | None] = mapped_column(Integer)
    sources_avg_score: Mapped[float | None] = mapped_column(Float)
    source_types: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    # Agent details
    perspectives_used: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    agents_invoked: Mapped[list[str] | None] = mapped_column(ARRAY(String))
    tool_calls: Mapped[list[dict] | None] = mapped_column(JSONB)

    # Confidence
    confidence_score: Mapped[float | None] = mapped_column(Float)
    escalation_required: Mapped[bool] = mapped_column(Boolean, default=False)
    escalation_reason: Mapped[str | None] = mapped_column(String(255))

    # === OUTCOME TRACKING ===
    # Explicit feedback
    feedback_rating: Mapped[int | None] = mapped_column(Integer)  # 1 (down) or 5 (up)
    feedback_comment: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None] = mapped_column()

    # Implicit signals
    had_follow_up: Mapped[bool | None] = mapped_column(Boolean)
    follow_up_interaction_id: Mapped[UUID | None] = mapped_column(ForeignKey("ai_interactions.id"))
    time_reading_ms: Mapped[int | None] = mapped_column(Integer)
    copied_response: Mapped[bool | None] = mapped_column(Boolean)

    # Action correlation
    action_type: Mapped[str | None] = mapped_column(String(100))
    action_entity_id: Mapped[UUID | None] = mapped_column()
    time_to_action_seconds: Mapped[int | None] = mapped_column(Integer)
    action_modified: Mapped[bool | None] = mapped_column(Boolean)

    # === PRIVACY ===
    consent_training: Mapped[bool] = mapped_column(Boolean, default=True)
    anonymized: Mapped[bool] = mapped_column(Boolean, default=False)
    raw_log_s3_key: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, index=True)

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_interactions")
    user = relationship("User", back_populates="ai_interactions")
    client = relationship("Client", back_populates="ai_interactions")

    __table_args__ = (
        Index("ix_ai_interactions_tenant_created", "tenant_id", "created_at"),
        Index("ix_ai_interactions_category_created", "category", "created_at"),
        Index("ix_ai_interactions_feedback", "tenant_id", "feedback_rating"),
    )
```

---

## 2. QueryPattern

Aggregated patterns identified from interaction clustering.

```python
class QueryPattern(Base):
    """Aggregated query patterns from clustering analysis."""
    __tablename__ = "query_patterns"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID | None] = mapped_column(ForeignKey("tenants.id"), index=True)
    # tenant_id = None for global patterns

    canonical_query: Mapped[str] = mapped_column(Text, nullable=False)
    pattern_embedding_id: Mapped[str] = mapped_column(String(100))

    category: Mapped[str] = mapped_column(String(50), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50))

    # Metrics
    occurrence_count: Mapped[int] = mapped_column(Integer, default=0)
    avg_satisfaction_score: Mapped[float | None] = mapped_column(Float)
    follow_up_rate: Mapped[float | None] = mapped_column(Float)

    # Opportunities
    suggested_kb_article: Mapped[str | None] = mapped_column(String(255))
    suggested_feature: Mapped[str | None] = mapped_column(String(255))
    auto_response_candidate: Mapped[bool] = mapped_column(Boolean, default=False)

    # Sample interactions for context
    sample_interaction_ids: Mapped[list[str] | None] = mapped_column(ARRAY(String))

    first_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    last_seen_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)

    __table_args__ = (
        Index("ix_query_patterns_category", "category", "occurrence_count"),
    )
```

---

## 3. KnowledgeGap

Identified areas where AI performance is low.

```python
class GapStatus(str, Enum):
    """Status of knowledge gap resolution."""
    IDENTIFIED = "IDENTIFIED"
    IN_PROGRESS = "IN_PROGRESS"
    RESOLVED = "RESOLVED"


class ResolutionType(str, Enum):
    """How the gap was resolved."""
    KB_ARTICLE = "KB_ARTICLE"
    FEATURE = "FEATURE"
    MODEL_UPDATE = "MODEL_UPDATE"
    PROMPT_IMPROVEMENT = "PROMPT_IMPROVEMENT"


class KnowledgeGap(Base):
    """Identified gaps in AI knowledge/capability."""
    __tablename__ = "knowledge_gaps"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)

    topic: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(50), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50))

    # Evidence
    sample_queries: Mapped[list[str]] = mapped_column(ARRAY(Text))
    interaction_count: Mapped[int] = mapped_column(Integer)
    avg_satisfaction: Mapped[float] = mapped_column(Float)

    # Priority
    priority_score: Mapped[float] = mapped_column(Float, index=True)

    # Resolution tracking
    status: Mapped[str] = mapped_column(String(50), default=GapStatus.IDENTIFIED)
    resolution_type: Mapped[str | None] = mapped_column(String(50))
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    resolution_entity_id: Mapped[UUID | None] = mapped_column()  # KB article ID, feature ID, etc.

    # Dates
    identified_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    resolved_at: Mapped[datetime | None] = mapped_column()

    # Post-resolution tracking
    satisfaction_after: Mapped[float | None] = mapped_column(Float)
    improvement_percentage: Mapped[float | None] = mapped_column(Float)

    __table_args__ = (
        Index("ix_knowledge_gaps_priority", "status", "priority_score"),
    )
```

---

## 4. FineTuningCandidate

Auto-identified high-quality interactions for potential training.

```python
class CandidateStatus(str, Enum):
    """Status in curation pipeline."""
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPORTED = "EXPORTED"


class FineTuningCandidate(Base):
    """Auto-identified high-quality interactions for fine-tuning."""
    __tablename__ = "fine_tuning_candidates"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_interactions.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Quality signals (auto-calculated)
    quality_score: Mapped[float] = mapped_column(Float, index=True)  # 0-1 composite
    has_positive_feedback: Mapped[bool] = mapped_column(Boolean, default=False)
    had_action_taken: Mapped[bool] = mapped_column(Boolean, default=False)
    no_follow_up_needed: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence_was_high: Mapped[bool] = mapped_column(Boolean, default=False)

    # Category for balanced sampling
    category: Mapped[str] = mapped_column(String(50), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50))

    # Curation status
    status: Mapped[str] = mapped_column(String(50), default=CandidateStatus.PENDING, index=True)

    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    reviewed_at: Mapped[datetime | None] = mapped_column()
    reviewed_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Relationships
    interaction = relationship("AIInteraction")

    __table_args__ = (
        Index("ix_candidates_status_score", "status", "quality_score"),
        Index("ix_candidates_category", "status", "category"),
    )
```

---

## 5. FineTuningExample

Human-curated, approved training examples.

```python
class FineTuningExample(Base):
    """Human-curated, approved examples ready for training."""
    __tablename__ = "fine_tuning_examples"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    interaction_id: Mapped[UUID] = mapped_column(
        ForeignKey("ai_interactions.id", ondelete="CASCADE"),
        index=True,
    )
    candidate_id: Mapped[UUID] = mapped_column(
        ForeignKey("fine_tuning_candidates.id", ondelete="CASCADE"),
        index=True,
    )

    # Training data (may be edited from original)
    system_prompt: Mapped[str] = mapped_column(Text, nullable=False)
    user_message: Mapped[str] = mapped_column(Text, nullable=False)  # Anonymized query
    ideal_response: Mapped[str] = mapped_column(Text, nullable=False)  # Original or improved

    # Edit tracking
    response_was_edited: Mapped[bool] = mapped_column(Boolean, default=False)
    original_response: Mapped[str | None] = mapped_column(Text)

    # Quality assessment
    quality_score: Mapped[int] = mapped_column(Integer)  # 1-5 human rating
    quality_notes: Mapped[str | None] = mapped_column(Text)

    # Curation tracking
    curated_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    curated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

    # Export tracking
    exported_in_version: Mapped[str | None] = mapped_column(String(50))
    exported_at: Mapped[datetime | None] = mapped_column()

    # Category for balanced sampling
    category: Mapped[str] = mapped_column(String(50), index=True)
    subcategory: Mapped[str | None] = mapped_column(String(50))

    # Relationships
    interaction = relationship("AIInteraction")
    candidate = relationship("FineTuningCandidate")
    curator = relationship("User")

    __table_args__ = (
        Index("ix_examples_category", "category", "quality_score"),
        Index("ix_examples_exported", "exported_in_version"),
    )
```

---

## 6. FineTuningDataset

Versioned JSONL exports for model training.

```python
class FineTuningDataset(Base):
    """Tracks exported JSONL dataset versions."""
    __tablename__ = "fine_tuning_datasets"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    version: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)

    # S3 locations (JSONL files)
    train_s3_key: Mapped[str] = mapped_column(String(255), nullable=False)
    eval_s3_key: Mapped[str] = mapped_column(String(255), nullable=False)

    # Stats
    total_examples: Mapped[int] = mapped_column(Integer)
    train_examples: Mapped[int] = mapped_column(Integer)
    eval_examples: Mapped[int] = mapped_column(Integer)
    category_distribution: Mapped[dict] = mapped_column(JSONB)  # {"COMPLIANCE": 450, ...}

    # Date range of source interactions
    source_date_start: Mapped[datetime] = mapped_column()
    source_date_end: Mapped[datetime] = mapped_column()

    # Training status
    training_started_at: Mapped[datetime | None] = mapped_column()
    training_completed_at: Mapped[datetime | None] = mapped_column()
    model_id: Mapped[str | None] = mapped_column(String(255))  # Resulting fine-tuned model

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    created_by: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    notes: Mapped[str | None] = mapped_column(Text)

    # Relationships
    creator = relationship("User")
```

---

## 7. TenantAISettings

Tenant-level privacy and learning preferences.

```python
class TenantAISettings(Base):
    """Tenant-level AI learning preferences."""
    __tablename__ = "tenant_ai_settings"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"),
        unique=True,
        index=True,
    )

    # Consent settings
    contribute_to_training: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_pattern_analysis: Mapped[bool] = mapped_column(Boolean, default=True)
    allow_anonymized_benchmarking: Mapped[bool] = mapped_column(Boolean, default=True)

    # Retention
    raw_log_retention_days: Mapped[int] = mapped_column(Integer, default=730)  # 2 years

    # Metadata
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    updated_by: Mapped[UUID | None] = mapped_column(ForeignKey("users.id"))

    # Relationships
    tenant = relationship("Tenant", back_populates="ai_settings")
```

---

## Indexes Summary

| Table | Index | Columns | Purpose |
|-------|-------|---------|---------|
| ai_interactions | ix_ai_interactions_tenant_created | tenant_id, created_at | Dashboard queries |
| ai_interactions | ix_ai_interactions_category_created | category, created_at | Pattern analysis |
| ai_interactions | ix_ai_interactions_feedback | tenant_id, feedback_rating | Feedback queries |
| query_patterns | ix_query_patterns_category | category, occurrence_count | Pattern dashboard |
| knowledge_gaps | ix_knowledge_gaps_priority | status, priority_score | Gap prioritization |
| fine_tuning_candidates | ix_candidates_status_score | status, quality_score | Curation queue |
| fine_tuning_candidates | ix_candidates_category | status, category | Balanced sampling |
| fine_tuning_examples | ix_examples_category | category, quality_score | Export sampling |
| fine_tuning_examples | ix_examples_exported | exported_in_version | Export tracking |

---

## Migration Notes

```python
# Alembic migration template
def upgrade():
    # 1. Create ai_interactions table
    op.create_table(
        "ai_interactions",
        # ... columns ...
    )

    # 2. Create dependent tables
    op.create_table("query_patterns", ...)
    op.create_table("knowledge_gaps", ...)
    op.create_table("fine_tuning_candidates", ...)
    op.create_table("fine_tuning_examples", ...)
    op.create_table("fine_tuning_datasets", ...)
    op.create_table("tenant_ai_settings", ...)

    # 3. Create indexes
    op.create_index(...)

    # 4. Add RLS policies
    op.execute("""
        ALTER TABLE ai_interactions ENABLE ROW LEVEL SECURITY;
        CREATE POLICY tenant_isolation ON ai_interactions
            FOR ALL USING (tenant_id = current_setting('app.current_tenant')::uuid);
    """)
```
